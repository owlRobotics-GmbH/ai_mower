# AI mower 

A camera-based (AI) robot mower that you can retrain yourself (within a few minutes) to your specific environment (small garden). It comes pre-trained to detect lawn/non-lawn, however you can retrain with the integrated web-interface by making example photos with the mower's camera (training lawn/non-lawn examples).

<img width="400" alt="image" src="https://github.com/user-attachments/assets/e26136c8-1d55-498d-adec-94559e20222e" />

<img width="400" alt="image" src="https://github.com/user-attachments/assets/722970a7-33bd-4e6d-8874-7c65266a3eca" />


## Requirements

- Your own robot mower chassis with motors, or: YardCare V100 chassis with DC gear motors and brushless mowing motor
- SMARTMOW/owlRobotics components: BLDC drivers (those also support DC motors)
- OrangePI5Pro (recommended) or Raspberry PI5 (with further changes)
- magnetic encoder (AS5600) for mowing motor
- USB camera module
- USB sound card module

## Installation
1. Install Ubuntu and CAN drivers on your OrangePI5Pro as described here: https://github.com/owlRobotics-GmbH/owlRobotPlatform
2. Type in Linux terminal:
   ```
   git clone https://github.com/owlRobotics-GmbH/ai_mower
   cd ai_mower
   install_orangepi5_cpu_deps.sh
   service.sh  (and choose start service)
   ```
3. launch 'http://orangepi5pro.local:8090' on a remote browser
4. Put mower on lawn and press 'START' via web UI or via robot STOP button (see video)
 
Example video:  

https://www.youtube.com/watch?v=QmxUNqRI3CY

## Forum (for parts, photos, discussions etc.)
https://forum.ardumower.de/threads/rasenroboter-software-für-kleingarten-kamera-umbau-yardcare-v100-auf-opensource.25658/






