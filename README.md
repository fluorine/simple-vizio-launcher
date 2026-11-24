# Simple Vizio Launcher

A quiet, remote-friendly home screen for a compatible Vizio TV. A small program on a computer on your home network serves three large app buttons and brings the screen back when the TV opens Vizio Home. The layout is intentionally easy to read from across the room, including for people who prefer fewer choices.

![Browser-rendered preview of the launcher, with three large app buttons and a small Vizio Home button](docs/launcher-preview.png)

*This is a browser-rendered screenshot of the actual page, not a photograph of the television.*

The idea is similar to [couch-tv](https://github.com/Seagey/couch-tv), another project exploring quieter TV home screens. This project is a small, separate Vizio-focused implementation; see [couch-tv's Vizio notes](https://github.com/Seagey/couch-tv/blob/main/docs/VIZIO.md) for its own beta approach and compatibility information.

## What it does

- Shows YouTube, Netflix and Prime Video in a large, high-contrast row. A smaller Vizio Home button opens the original home screen.
- Uses the television remote's arrows and OK. Remembers the last focused app across visits; the Vizio Home button is excluded.
- Checks the TV power state before watching apps, then opens the simple screen when Vizio Home is active. A remote Home or app button can wake the TV; the launcher responds after it reports as on. Optionally redirects WatchFree to YouTube while the TV is on.
- Includes an experimental separate command to serve one specified local video to a TV-sized player, without adding a video library to the launcher.
- Includes an [agent skill](skills/vizio-launcher/SKILL.md) for setup, troubleshooting and local video requests.

## Status and limitations

This is experimental, not affiliated with Vizio, Netflix, YouTube, or Amazon. The launcher uses undocumented Vizio OS behavior; firmware changes and other models may work differently. It does not replace the TV OS, remove ads inside apps, or install itself on the TV.

On one **VQD55M-0804**, firmware **86.920.9.3-2**, a prototype displayed the screen, responded to the remote, launched YouTube and Prime Video, remembered selection, opened the original home, and redirected WatchFree to YouTube. The approach is not necessarily limited to that model, but other models and the generalized pairing/setup workflow have not been verified on hardware. App identifiers can vary by model; Netflix has not been independently confirmed on that TV.

The computer must be on, signed in, awake and on the same network. The launcher checks `/state/device/power_mode` and does not issue app-launch commands unless the TV reports power mode `1` (on); if the power state cannot be read, it waits. This avoids treating a stale Home app value in standby as an instruction to launch the page. A remote Home or app button can wake the TV, after which the launcher may open its simple screen when it sees Vizio Home. Once you intentionally enter Vizio Home, a second Home press while already there cannot be distinguished by the current polling approach; open an app and then press Home to return to the simple screen. When the service is stopped, the original home remains available. If the computer goes to sleep while the custom page is open, press the TV's Home button to return to Vizio Home.

Local video: H.264/AAC MP4 clips, including a 1080p sample, played on the same TV. The owner confirmed the screen-filling player, progress bar, and 5-second seeking while paused. Other video formats remain unverified. Codec support depends on the TV. This is not a file browser, transcoder, or permanent launcher tile.

## Set up

### Recommended: ask an AI assistant to configure it

If your AI assistant can read local files and run commands on your computer, give it the path to your downloaded repository and this prompt. The assistant can walk through the setup, do the computer-side work, and pause when it needs you to read a code from the TV or confirm a system setting.

> I want you to set up Simple Vizio Launcher from this repository on my computer and TV. The repository folder is: **https://github.com/fluorine/simple-vizio-launcher**. If I have not given you a usable folder path, ask me for it first.
>
> Read the repository README and inspect the project before making changes. Check my operating system, Python version, network setup, and the launcher's current files. Install only dependencies the project actually needs. Help me find the TV's local IP address using its network information, then pair it with the launcher. Tell me when to look at the TV for the pairing code and let me enter that code locally; never ask me to paste or reveal the pairing token. Keep `config.json` private and out of version control.
>
> Start the launcher and guide me to open Vizio Home so we can confirm the simple screen appears and the remote can launch an app. If I want it to work without this AI or a terminal open, configure the documented per-user startup option for my operating system so it starts after I sign in. Before changing startup or firewall settings, explain the specific change and ask me to approve it. Allow network access only on my trusted private home network if needed. Do not change router settings, expose a port to the internet, or send custom URLs to undocumented TV app IDs. Make sure I can stop and uninstall the launcher, and show me how.
>
> Keep troubleshooting steps focused on this repository. Do not print, upload, commit, or send pairing tokens, passwords, serial numbers, MAC addresses, household IP details, logs, or private media. Verify each step with me, distinguish what we confirmed on the TV from what is only configured on the computer, and tell me what requires the computer to stay on, signed in, and awake.

The pairing code must be read from the TV by you and entered locally when prompted. The assistant should not need your router password or TV account password. The computer and TV must be on the same trusted network. To have the launcher start without Codex, the computer still needs to be on, signed in, and awake. The Windows startup installer has not yet been tested end-to-end after a fresh sign-in.

### Manual setup

1. Install Python 3.10 or later. Put this folder on a computer on the same trusted home network as the TV. Leave the TV on.
2. Find the TV's local IPv4 address in its network information. If possible, reserve its address in your router so it does not change.
3. In a terminal in this folder, pair with the TV (replace the example address with yours):

   ```sh
   python launcher.py pair 192.168.1.50
   ```

   Enter the four-digit code shown on the TV. This writes `config.json`, which contains a secret pairing token. Keep it private. The program will not overwrite an existing config; move or back it up before pairing again.
4. Start the service:

   ```sh
   python launcher.py run
   ```

   Open the TV's Vizio Home screen. The simple screen should appear after a few seconds. Keep the process running. On Windows, allow Python access to the **private** network if the firewall prompts you.
5. Stop it with Ctrl+C. When stopped, the TV's standard home remains available.

To start it automatically after signing in, use your operating system's normal startup facility. On Windows, after pairing and testing the launcher manually, run in PowerShell from this folder:

```powershell
./install-startup.ps1
```

This adds a startup entry for the current Windows account, so Python runs the launcher in the background without Codex or a terminal window. Sign in after a restart and keep the computer awake. Moving this folder or Python later will break the saved startup path; run the installer again after moving. To remove the startup entry, run `./install-startup.ps1 -Remove`; stop an already running launcher separately. The packaged installer and a fresh Windows sign-in have not yet been tested end-to-end.

Alternatively, create a shortcut in the current user's Startup folder (`Win+R`, then `shell:startup`) that runs `pythonw.exe` with the full path to `launcher.py` and argument `run`. Use absolute paths.

## Options

After pairing, `config.json` contains the TV address, port, app identifiers and `redirect_watchfree`. Set `redirect_watchfree` to `true` to send the TV to YouTube whenever WatchFree opens. This detects the app state, so it affects *all* ways of opening WatchFree, not just the remote button. The TV and computer addresses need to remain reachable; pair again if the TV forgets the token.

App launch IDs are firmware-dependent. The included Prime Video ID is `[3, "3"]`; another common ID is `[2, "4"]`. If an app does not open, verify it works from Vizio Home and consult the [Vizio control research](https://github.com/exiva/Vizio_SmartCast_API) or your TV's current app information. Do not assume a `SUCCESS` response proves the app appeared.

## Play a local video

With the TV paired and a local file available, run:

```sh
python video.py "/path/to/your/video.mp4"
```

Use the path to an existing MP4, M4V, or WebM file; only that chosen file is served, temporarily. The TV should show the video across the screen. The intended remote controls are OK to pause/play, Left/Right to seek 5 seconds, and Home to exit. A progress bar appears during interaction. Keep the command running while watching and stop it with Ctrl+C afterward. Autoplay may be blocked, in which case press OK. These controls are experimental; try a short file first. The launcher service must be running for Home to return to the simple menu.

For a video later, give the assistant the local path and ask it to use the separate video command. Never paste passwords or pairing tokens into a public issue or chat.

To customize the launcher, tell your assistant what you want to see or change. For example:

> Change my Simple Vizio Launcher so the buttons are larger, put my favorite app first, and use a dark blue background. Keep the original Vizio Home option available. Show me the changes and test the remote navigation before replacing my running version.

You can also ask for different apps, colors, button arrangements, selection behavior, or remote shortcuts. The assistant should check which app controls are actually available on your model and distinguish a tested result from a proposed change. The [included skill](skills/vizio-launcher/SKILL.md) gives compatible agents the project-specific context.

## Security and privacy

- The pairing token is stored in plaintext in ignored `config.json`. Protect your computer account and never publish the file. Logs and selection files are also ignored.
- HTTP traffic stays on the local network but is **not encrypted**. The service binds to the local interface and checks the requesting TV's IP and request origin; an IP address is not strong authentication. Only use it on a trusted LAN. Never port-forward the service or the TV control port to the internet.
- The webview used for the page is a privileged system component on related Vizio OS devices. Serve only trusted pages. Do not send a custom URL to namespace 4 app ID 1: research reports that can persist and damage the TV's home UI. This project uses app ID 3001 for temporary pages. See [couch-tv's Vizio notes](https://github.com/Seagey/couch-tv/blob/main/docs/VIZIO.md) and [SmartCast webview research](https://github.com/vindeckyy/smartcast-backdoor).
- The TV's local HTTPS certificate is not publicly trusted, so the code disables certificate verification for TV control. This assumes a trusted local network and correct TV address.

## For agents and contributors

Read [the agent skill](skills/vizio-launcher/SKILL.md). Never commit tokens, IP addresses from a real household, private videos or local logs. Test changes using a stand-in or with the TV owner's permission, and distinguish API success from an actual on-screen result. Please include TV model and firmware **without serial numbers, MAC addresses or tokens** when reporting compatibility.
