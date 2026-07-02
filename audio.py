from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent
STARTUP_SOUND = ROOT / "tts" / "sheep.mp3"
SHUTDOWN_SOUND = ROOT / "tts" / "shutdown.mp3"
STOP_BUTTON_PROMPT_SOUNDS = {
    "start": ROOT / "tts" / "en_start.mp3",
    "shutdown": ROOT / "tts" / "en_shutdown.mp3",
    "reboot": ROOT / "tts" / "en_reboot.mp3",
    "mowing_off": ROOT / "tts" / "en_mowing_off.mp3",
    "mowing_on": ROOT / "tts" / "en_mowing_on.mp3",
}
ROBOT_START_SOUND = ROOT / "tts" / "eguitar.mp3"
ROBOT_STOP_SOUND = ROOT / "tts" / "stop.mp3"
ROBOT_SHEEP_SOUND = ROOT / "tts" / "sheep.mp3"
ROBOT_EVENT_SOUNDS = {
    "no_lawn": ROOT / "tts" / "en_no_lawn.mp3",
    "drive_stuck": ROOT / "tts" / "en_drive_stuck.mp3",
    "turn_stuck": ROOT / "tts" / "en_turn_stuck.mp3",
}
DEFAULT_STARTUP_SOUND_GAIN = 1.0
ES8388_CARD = os.environ.get("AI_MOWER_AUDIO_CARD", "2")
USB_AUDIO_CARD = os.environ.get("AI_MOWER_USB_AUDIO_CARD", "3")
PULSE_SERVER = os.environ.get("PULSE_SERVER", "")
PULSE_SINK = os.environ.get("AI_MOWER_PULSE_SINK", "").strip()
ALSA_DEVICE = os.environ.get("AI_MOWER_ALSA_DEVICE", "").strip()


def startup_sound_gain() -> float:
    raw = os.environ.get("AI_MOWER_STARTUP_SOUND_GAIN", str(DEFAULT_STARTUP_SOUND_GAIN))
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_STARTUP_SOUND_GAIN


def shutdown_sound_gain() -> float:
    raw = os.environ.get("AI_MOWER_SHUTDOWN_SOUND_GAIN", str(DEFAULT_STARTUP_SOUND_GAIN))
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_STARTUP_SOUND_GAIN


def robot_sound_gain() -> float:
    raw = os.environ.get("AI_MOWER_ROBOT_SOUND_GAIN", str(DEFAULT_STARTUP_SOUND_GAIN))
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_STARTUP_SOUND_GAIN


def set_system_volume_full() -> None:
    amixer = shutil.which("amixer")
    if not amixer:
        return

    for control in ("Master", "PCM", "Speaker"):
        subprocess.run(
            [amixer, "set", control, "100%", "unmute"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    for args in (
        ["-c", ES8388_CARD, "set", "PCM", "100%"],
        ["-c", ES8388_CARD, "set", "Output 1", "100%"],
        ["-c", ES8388_CARD, "set", "Output 2", "100%"],
        ["-c", ES8388_CARD, "set", "Speaker", "on"],
        ["-c", ES8388_CARD, "set", "Headphone", "on"],
        ["-c", USB_AUDIO_CARD, "set", "PCM", "100%", "unmute"],
    ):
        subprocess.run(
            [amixer, *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def player_commands(path: Path, gain: float) -> tuple[tuple[str, list[str]], ...]:
    gain = max(0.0, gain)
    return (
        ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet", "-af", f"volume={gain}", str(path)]),
        ("mpv", ["--no-video", "--really-quiet", f"--volume={int(100 * gain)}", str(path)]),
        ("cvlc", ["--play-and-exit", "--quiet", f"--gain={gain}", str(path)]),
        ("mpg123", ["-q", str(path)]),
        ("mpg321", ["-q", str(path)]),
    )


def selected_pulse_sink() -> str:
    if PULSE_SINK:
        return PULSE_SINK

    pactl = shutil.which("pactl")
    if not pactl:
        return ""

    args = [pactl]
    if PULSE_SERVER:
        args.append(f"--server={PULSE_SERVER}")
    args.extend(["list", "short", "sinks"])
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            timeout=2.0,
            check=False,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return ""
    if result.returncode != 0:
        return ""

    sinks = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2:
            sinks.append(fields[1])
    if not sinks:
        return ""

    for needle in ("usb", "uac", "es8388"):
        for sink in sinks:
            if needle in sink.lower():
                return sink
    for sink in sinks:
        name = sink.lower()
        if "hdmi" not in name and "dp0" not in name:
            return sink
    return sinks[0]


def pulse_available() -> bool:
    pactl = shutil.which("pactl")
    if not pactl:
        return False

    args = [pactl]
    if PULSE_SERVER:
        args.append(f"--server={PULSE_SERVER}")
    args.append("info")
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            timeout=2.0,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def paplay_command(path: str) -> tuple[list[str], str]:
    paplay = shutil.which("paplay")
    if not paplay:
        return [], ""

    args = [paplay]
    if PULSE_SERVER:
        args.append(f"--server={PULSE_SERVER}")
    sink = selected_pulse_sink()
    if sink:
        args.append(f"--device={sink}")
    args.append(path)
    return args, sink


def paplay_pipeline(path: Path, gain: float = 1.0) -> tuple[subprocess.Popen | None, str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("paplay"):
        return None, ""
    if not pulse_available():
        return None, ""

    wav = tempfile.NamedTemporaryFile(prefix="ai-mower-startup-", suffix=".wav", delete=False)
    wav_path = wav.name
    wav.close()
    result = subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-af",
            f"volume={max(0.0, gain)}",
            wav_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        Path(wav_path).unlink(missing_ok=True)
        return None, ""

    paplay_args, sink = paplay_command(wav_path)
    play = subprocess.Popen(
        ["sh", "-c", '"$1" "${@:2}"; rm -f "${@: -1}"', "ai-mower-paplay", *paplay_args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        executable="/bin/bash",
        text=True,
    )
    try:
        play.communicate(timeout=0.25)
    except subprocess.TimeoutExpired:
        return play, sink
    if play.returncode == 0:
        return play, sink
    return None, sink


def alsa_devices() -> tuple[str, ...]:
    if ALSA_DEVICE:
        return (ALSA_DEVICE,)
    return (
        f"plughw:CARD=UACDemoV10,DEV=0",
        f"plughw:CARD={USB_AUDIO_CARD},DEV=0",
        f"plughw:CARD=rockchipes8388,DEV=0",
        f"plughw:CARD={ES8388_CARD},DEV=0",
    )


def aplay_pipeline(path: Path, gain: float = 1.0) -> tuple[subprocess.Popen | None, str]:
    ffmpeg = shutil.which("ffmpeg")
    aplay = shutil.which("aplay")
    if not ffmpeg or not aplay:
        return None, ""

    for device in alsa_devices():
        wav = tempfile.NamedTemporaryFile(prefix="ai-mower-startup-", suffix=".wav", delete=False)
        wav_path = wav.name
        wav.close()
        result = subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-af",
                f"volume={max(0.0, gain)}",
                wav_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode != 0:
            Path(wav_path).unlink(missing_ok=True)
            return None, ""

        play = subprocess.Popen(
            ["sh", "-c", '"$1" "${@:2}"; rm -f "${@: -1}"', "ai-mower-aplay", aplay, "-D", device, wav_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            executable="/bin/bash",
            text=True,
        )
        try:
            play.communicate(timeout=0.25)
        except subprocess.TimeoutExpired:
            return play, device
        Path(wav_path).unlink(missing_ok=True)
        if play.returncode == 0:
            return play, device

    return None, ""


def play_sound_with_paplay(path: Path, gain: float = 1.0, timeout: float | None = None) -> tuple[str | None, str]:
    if not path.exists():
        return None, "sound file missing"
    ffmpeg = shutil.which("ffmpeg")
    paplay = shutil.which("paplay")
    if not ffmpeg or not paplay:
        return None, "ffmpeg or paplay missing"
    if not pulse_available():
        return None, "pulse unavailable"

    try:
        wav = tempfile.NamedTemporaryFile(prefix="ai-mower-startup-", suffix=".wav", delete=False)
        wav_path = wav.name
        wav.close()
        decode = subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-af",
                f"volume={max(0.0, gain)}",
                wav_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if decode.returncode != 0:
            Path(wav_path).unlink(missing_ok=True)
            error = (decode.stderr or b"").decode("utf-8", "replace").strip() or f"ffmpeg return code {decode.returncode}"
            return None, error
        paplay_args, sink = paplay_command(wav_path)
        play = subprocess.Popen(
            paplay_args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=False,
        )
        try:
            _, play_stderr = play.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            play.kill()
            play.communicate()
            Path(wav_path).unlink(missing_ok=True)
            return None, "paplay timed out"
        Path(wav_path).unlink(missing_ok=True)
    except subprocess.TimeoutExpired:
        return None, "paplay timed out"
    except Exception as exc:
        return None, f"paplay pipeline: {exc}"

    errors = []
    if play.returncode not in (0, None):
        errors.append((play_stderr or b"").decode("utf-8", "replace").strip() or f"paplay return code {play.returncode}")
    if errors:
        return None, "; ".join(errors)
    return f"paplay:{sink}" if sink else "paplay", ""


def play_sound_with_aplay(path: Path, gain: float = 1.0, timeout: float | None = None) -> tuple[str | None, str]:
    if not path.exists():
        return None, "sound file missing"
    ffmpeg = shutil.which("ffmpeg")
    aplay = shutil.which("aplay")
    if not ffmpeg or not aplay:
        return None, "ffmpeg or aplay missing"

    last_error = ""
    for device in alsa_devices():
        wav = tempfile.NamedTemporaryFile(prefix="ai-mower-startup-", suffix=".wav", delete=False)
        wav_path = wav.name
        wav.close()
        decode = subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-af",
                f"volume={max(0.0, gain)}",
                wav_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if decode.returncode != 0:
            Path(wav_path).unlink(missing_ok=True)
            last_error = (decode.stderr or b"").decode("utf-8", "replace").strip() or f"ffmpeg return code {decode.returncode}"
            break

        play = subprocess.Popen(
            [aplay, "-D", device, wav_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=False,
        )
        try:
            _, play_stderr = play.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            play.kill()
            play.communicate()
            Path(wav_path).unlink(missing_ok=True)
            return None, "aplay timed out"
        Path(wav_path).unlink(missing_ok=True)
        if play.returncode == 0:
            return f"aplay:{device}", ""
        last_error = (play_stderr or b"").decode("utf-8", "replace").strip() or f"aplay return code {play.returncode}"

    return None, last_error


def play_app_sound(path: Path, gain: float = 1.0, *, blocking: bool = False, timeout: float = 8.0) -> tuple[str | None, str]:
    if not path.exists():
        return None, "sound file missing"

    last_error = ""
    if blocking:
        if shutil.which("ffmpeg") and shutil.which("paplay"):
            player, error = play_sound_with_paplay(path, gain=gain, timeout=timeout)
            if player:
                return player, ""
            last_error = error or "paplay failed"
        if shutil.which("ffmpeg") and shutil.which("aplay"):
            player, error = play_sound_with_aplay(path, gain=gain, timeout=timeout)
            if player:
                return player, ""
            last_error = error or last_error or "aplay failed"
    else:
        paplay, sink = paplay_pipeline(path, gain=gain)
        if paplay:
            return f"paplay:{sink}" if sink else "paplay", ""
        aplay, device = aplay_pipeline(path, gain=gain)
        if aplay:
            return f"aplay:{device}", ""

    for binary, args in player_commands(path, gain):
        player = shutil.which(binary)
        if not player:
            continue
        if blocking:
            try:
                result = subprocess.run(
                    [player, *args],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    timeout=timeout,
                    check=False,
                    text=True,
                )
            except subprocess.TimeoutExpired:
                last_error = f"{binary}: timed out"
                continue
            except Exception as exc:
                last_error = f"{binary}: {exc}"
                continue
            if result.returncode == 0:
                return binary, ""
            last_error = f"{binary}: {(result.stderr or f'return code {result.returncode}').strip()}"
            continue

        try:
            subprocess.Popen(
                [player, *args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
        except Exception as exc:
            last_error = f"{binary}: {exc}"
            continue
        return binary, ""

    return None, last_error or "no sound player available"


def play_sound(path: Path, gain: float = 1.0) -> str | None:
    if not path.exists():
        return None

    player, _ = play_app_sound(path, gain=gain, blocking=False)
    return player


def play_sound_blocking(path: Path, gain: float = 1.0, timeout: float = 8.0) -> str | None:
    if not path.exists():
        return None

    player, _ = play_app_sound(path, gain=gain, blocking=True, timeout=timeout)
    return player


def play_sound_checked(path: Path, gain: float = 1.0, timeout: float = 8.0) -> tuple[str | None, str]:
    return play_app_sound(path, gain=gain, blocking=True, timeout=timeout)


def play_startup_sound(add_log: Callable[..., None]) -> None:
    if not STARTUP_SOUND.exists():
        add_log("error", f"startup sound missing: {STARTUP_SOUND.relative_to(ROOT)}")
        return

    set_system_volume_full()
    gain = startup_sound_gain()
    player, error = play_app_sound(STARTUP_SOUND, gain=gain, blocking=False)
    if player:
        add_log(
            "system",
            f"startup sound played: {STARTUP_SOUND.relative_to(ROOT)} gain={gain:g} player={player}",
        )
        return

    add_log("error", f"startup sound failed: {error}")


def play_shutdown_sound(add_log: Callable[..., None]) -> None:
    if not SHUTDOWN_SOUND.exists():
        add_log("error", f"shutdown sound missing: {SHUTDOWN_SOUND.relative_to(ROOT)}")
        return

    set_system_volume_full()
    gain = shutdown_sound_gain()
    player, error = play_app_sound(SHUTDOWN_SOUND, gain=gain, blocking=True)
    if player:
        add_log(
            "system",
            f"shutdown sound played: {SHUTDOWN_SOUND.relative_to(ROOT)} gain={gain:g} player={player}",
        )
        return

    add_log("error", f"shutdown sound failed: {error}")


def play_stop_button_prompt(name: str, add_log: Callable[..., None] | None = None, *, blocking: bool = False) -> None:
    sound = STOP_BUTTON_PROMPT_SOUNDS.get(name)
    if sound is None:
        if add_log:
            add_log("error", f"STOP prompt unknown: {name}")
        return
    if not sound.exists():
        if add_log:
            add_log("error", f"STOP prompt sound missing: {sound.relative_to(ROOT)}")
        return

    player, error = play_app_sound(sound, gain=robot_sound_gain(), blocking=blocking)
    if player:
        if add_log:
            add_log("robot", f"STOP prompt sound played: {sound.relative_to(ROOT)} player={player}")
        return
    if add_log:
        add_log("error", f"STOP prompt sound failed: {error}")


def play_robot_start_sound(add_log: Callable[..., None]) -> None:
    if not ROBOT_START_SOUND.exists():
        add_log("error", f"robot start sound missing: {ROBOT_START_SOUND.relative_to(ROOT)}")
        return

    player, error = play_app_sound(ROBOT_START_SOUND, gain=robot_sound_gain(), blocking=False)
    if player:
        add_log("robot", f"robot start sound played: {ROBOT_START_SOUND.relative_to(ROOT)} player={player}")
        return

    add_log("error", f"robot start sound failed: {error}")


def play_robot_stop_sound(add_log: Callable[..., None]) -> None:
    if not ROBOT_STOP_SOUND.exists():
        add_log("error", f"robot stop sound missing: {ROBOT_STOP_SOUND.relative_to(ROOT)}")
        return

    player, error = play_app_sound(ROBOT_STOP_SOUND, gain=robot_sound_gain(), blocking=False)
    if player:
        add_log("robot", f"robot stop sound played: {ROBOT_STOP_SOUND.relative_to(ROOT)} player={player}")
        return

    add_log("error", f"robot stop sound failed: {error}")


def play_robot_sheep_sound(add_log: Callable[..., None]) -> None:
    if not ROBOT_SHEEP_SOUND.exists():
        add_log("error", f"robot sheep sound missing: {ROBOT_SHEEP_SOUND.relative_to(ROOT)}")
        return

    player, error = play_app_sound(ROBOT_SHEEP_SOUND, gain=robot_sound_gain(), blocking=False)
    if player:
        add_log("robot", f"robot sheep sound played: {ROBOT_SHEEP_SOUND.relative_to(ROOT)} player={player}")
        return

    add_log("error", f"robot sheep sound failed: {error}")


def play_robot_event_sound(name: str, add_log: Callable[..., None]) -> None:
    sound = ROBOT_EVENT_SOUNDS.get(name)
    if sound is None:
        add_log("error", f"robot event sound unknown: {name}")
        return
    if not sound.exists():
        add_log("error", f"robot event sound missing: {sound.relative_to(ROOT)}")
        return

    player, error = play_app_sound(sound, gain=robot_sound_gain(), blocking=False)
    if player:
        add_log("robot", f"robot event sound played: {sound.relative_to(ROOT)} event={name} player={player}")
        return

    add_log("error", f"robot event sound failed: {name}: {error}")
