# Tiamat

Tiamat is a keyboard-first terminal application that provides utility functions for the League of Legends client, inspired by [KbotExt](https://github.com/KebsCS/KBotExt/), by Kebs.

The interface opens immediately, detects the League Client in the background, and keeps module state and recent activity visible in one workspace.

![Tiamat menu interface](https://i.imgur.com/coZgPY9.png)

## ⚠️ Important Notice
Use at your own risk, as some features might violate Riot Games' Terms of Service.

## 🌟 Features

### Customization
* Icon Changer
  * Icon Changer (Icons 1-100)
  * Client Only (All Available Icons)
* Profile Background Changer
* Riot ID Changer

### Game Automation
* Auto Accept Match
* Ragequeue with selectable lobby type
* Autopick Champion
* Autoban Champion
* Smart Dodge (Avoid client restart)

### Utility
* Lobby Reveal
* Restart Client UX
* Disconnect from chat (toggle offline)

## 🚀 Installation

### Releases

You can find the most recent release [here](https://github.com/369gabriel/tiamat/releases).

### Prerequisites
- Python 3.10 or higher
- League of Legends client installed
- Git (for cloning the repository)

### Quick Start
1. Clone this repository:
```bash
git clone https://github.com/gyaaf/tiamat.git
```

2. Navigate to the project directory:
```bash
cd tiamat
```

3. Install required dependencies:
```bash
uv sync
```

4. Run the application:
```bash
uv run python tiamat/main.py
```

Run tests with:
```bash
uv run pytest
```

## 💡 Usage

### First Time Setup
1. Start Tiamat.
2. Launch the League of Legends client before or after Tiamat.
3. Select a module with the arrow keys, mouse, or its number shortcut.

### Keyboard Shortcuts

| Key | Action |
| --- | --- |
| `Up` / `Down` or `j` / `k` | Navigate modules |
| `Enter` | Open or run the selected module |
| `Space` | Toggle the selected automation |
| `/` | Search modules |
| `1` through `16`, then `Enter` | Open or run a module directly |
| `99`, then `Enter` or `q` | Exit |
| `Esc` | Close a form or confirmation |
| Left click | Open or run a module |
| Right click | Toggle an automation |


### Module Guide

| Number | Category | Module |
| --- | --- | --- |
| `1` | Automation | Auto Accept |
| `2` | Automation | Instalock |
| `3` | Automation | AutoBan |
| `4` | Automation | Ragequeue |
| `5` | Customization | Profile Icon |
| `6` | Customization | Client-Only Icon |
| `7` | Customization | Profile Background |
| `8` | Customization | Riot ID |
| `9` | Customization | Profile Badges |
| `10` | Customization | Status Message |
| `11` | Game Tools | Lobby Reveal |
| `12` | Game Tools | Dodge |
| `13` | Game Tools | Restart Client UX |
| `14` | Social | Disconnect Chat |
| `15` | Social | Remove All Friends |
| `16` | Settings | Configuration |

Configuration forms validate input inline. Destructive actions require confirmation before execution, and network work runs in the background so the interface remains responsive.

Ragequeue supports League queues plus TFT Normal, Ranked, Hyper Roll, and Double Up. Role preferences are automatically hidden and skipped for ARAM and TFT modes.

Configuration supports Porofessor, OP.GG, and U.GG for Lobby Reveal, plus independent `0-2s` delays for Auto Accept, Instalock, and AutoBan.

## 🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📫 Support
If you have any questions, suggestions, or complaints:
- Discord: gabrielgyaf
- Create an [Issue](https://github.com/gyaaf/tiamat/issues)

## 🙏 Acknowledgments
* [KbotExt](https://github.com/KebsCS/KBotExt/) by Kebs for inspiration
* All contributors and users of Tiamat
