# AIO LCD Unchained

WARNING: i'm not responsible for any damage to your equipment. If anything get stuck your best option is to turn off your pc and disconnect it from power for a minute or two before restarting it.

## Full app roadmap

- Configuration:
  - [x] SignalRGB configuration
  - [ ] Webinterface/Electron app for complete configuration
- Stats sources:
  - [x] AIO itsels
  - [x] CPU Usage
  - [ ] LibreHardwareMonitor
  - [ ] AIDA ?
- Background:
  - [x] SignalRGB
  - [ ] Static image
  - [ ] Single Gif
  - [ ] Gif/Static slideshow
- Overlay:
  - [x] Temperature metric
  - [ ] Other devices temperatures / stats
  - [x] Static circle
  - [ ] Other static shapes / Generic PNG
  - [x] Spinner based on metrics
  - [x] Static text
  - [ ] Dynamic text
  - [ ] Clock
  - [ ] Music ticket
  - [x] [Cider](https://cider.sh) Integration
- Devices:
  - [x] NZXT Kraken 2024 Elite
  - [x] NZXT Kraken 2023 Elite
  - [ ] NZXT Kraken 2023
  - [x] NZXT Kraken Z3
  - [ ] Corsair Capellix
  - Suggest a device by raising an Issue !

## Status

Check this youtube video to see latest status of SignalRGB integration:

[![Status](http://img.youtube.com/vi/-EUDxjzwlcg/0.jpg)](http://www.youtube.com/watch?v=-EUDxjzwlcg 'Kraken Elite SignalRGB')

## Installation

Download latest executable from github releases run it and restart signalrgb.
The app adds an icon to the systray that can be left clicked

## Development

You must have python 3.11 and rust installed in your system

checkout the repository or download the latest code and install python dependencies

```
pip install -r requirements.txt --upgrade
```

build and install the q565 image compressor using rust

```
maturin build --release
pip install ./target/wheels/q565_rust-0.1.0-cp311-none-win_amd64.whl --force-reinstall
```

## Usage

Ensure NZXT CAM / Other proprietary software is closed and start one of the available functions:

### Write GIF demo:

Writes a gif (static or animated) to the device

```
python writeGif.py path/to/your/file.gif
```

### Rotating demo:

Simple animation with frames generated in realtime:

```
python rotating.py
```

### Screencap demo:

Captures an area of your screen and renders it in the kraken elit lcd

```
python screencap.py
```

### Signalrgb demo:

Receives a canvas section from signalRGB, adds temperature infos and display it on the device

```
python signalrgb.py
```

## Images

Remote desktop icons created by fzyn - Flaticon https://www.flaticon.com/free-icons/remote-desktop"
Kraken device images taken from NZXT website

## License

MIT License

Copyright (c) 2023 Marco Massarotto

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
