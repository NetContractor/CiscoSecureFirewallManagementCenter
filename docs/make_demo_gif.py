"""Generates docs/demo.gif: a synthetic terminal recording of a fmc-setup session.

Run with: python docs/make_demo_gif.py
Not part of the package - a one-off asset generator, kept for reproducibility.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 980, 620
FONT_PATH = r"C:\Windows\Fonts\consola.ttf"
FONT_SIZE = 16
LINE_HEIGHT = 22
MARGIN_X = 22
TOP_BAR_H = 36
TEXT_TOP = TOP_BAR_H + 16
MAX_VISIBLE = (HEIGHT - TEXT_TOP - 10) // LINE_HEIGHT

BG = (18, 18, 20)
BAR_BG = (45, 45, 48)
PROMPT = (97, 214, 214)
TEXT = (212, 212, 212)
INPUT = (229, 192, 123)
OK = (152, 195, 121)
DIM = (120, 120, 120)
ACCENT = (198, 120, 221)

font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
font_bold = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", FONT_SIZE)

MENU = [
    ("1. Register new FTD devices from the xlsx", TEXT),
    ("2. Configure interfaces from the xlsx", TEXT),
    ("3. Add security zones from the xlsx", TEXT),
    ("4. Add new Access Control Policy", TEXT),
    ("5. Add categories from the xlsx", TEXT),
    ("6. Add ports from the xlsx", TEXT),
    ("7. Add port groups from the xlsx", TEXT),
    ("8. Add host, network or range from the xlsx", TEXT),
    ("9. Add network group from the xlsx", TEXT),
    ("10. Add ACP from the xlsx", TEXT),
    ("11. Export policy to the csv", TEXT),
    ("12. Export FMC configuration to the xlsx", TEXT),
    ("13. Add HA", TEXT),
    ("14. Add Port-Channel", TEXT),
    ("15. Add subinterface to Port-Channel", TEXT),
    ("16. END program", TEXT),
]

LINES = [
    ("$ fmc-setup --host fmc.example.com --username api-user", PROMPT),
    ("Password: ", TEXT),
    ("", TEXT),
    ("What would you like to do? Please select one of the following option: ", TEXT),
    ("", TEXT),
    *MENU,
    ("", TEXT),

    ("Please select option number: 1", INPUT),
    ("Registering new FTD devices from the xlsx", DIM),
    ("Access Control Policy 'Example_ACP' does not exist on FMC - creating it.", DIM),
    ("FTD-1 registration has been submitted to FMC.", OK),
    ("Waiting for FTD-1 registration to complete...", DIM),
    ("FTD-1 has been registered successfully.", OK),
    ("FTD-2 has been registered successfully.", OK),
    ("", TEXT),

    ("Please select option number: 2", INPUT),
    ("Configuring interfaces from the xlsx", DIM),
    ("Interface GigabitEthernet0/0 (OUTSIDE-IF) has been configured on FTD-1.", OK),
    ("Interface GigabitEthernet0/1 (DMZ-IF) has been configured on FTD-1.", OK),
    ("", TEXT),

    ("Please select option number: 3", INPUT),
    ("Adding Security Zones to FMC from the xlsx", DIM),
    ("Zone_Inside has been added to FMC.", OK),
    ("Zone_Outside has been added to FMC.", OK),
    ("Zone_DMZ has been added to FMC.", OK),
    ("", TEXT),

    ("Please select option number: 4", INPUT),
    ("Example_ACP", TEXT),
    ("Example_ACP has been added to FMC.", OK),
    ("", TEXT),

    ("Please select option number: 5", INPUT),
    ("Adding Categories to FMC from the xlsx", DIM),
    ("ACTIVE_DIRECTORY has been added to FMC.", OK),
    ("WEB has been added to FMC.", OK),
    ("MONITORING has been added to FMC.", OK),
    ("", TEXT),

    ("Please select option number: 6", INPUT),
    ("Adding new port from the xlsx", DIM),
    ("PING has been added to FMC.", OK),
    ("LDAP_TCP-389 has been added to FMC.", OK),
    ("… 7 more ports added", DIM),
    ("", TEXT),

    ("Please select option number: 7", INPUT),
    ("Adding new port group from the xlsx", DIM),
    ("LDAP_TCP-389, KERBEROS_TCP-88, … has been added to AD_PORTS", OK),
    ("", TEXT),

    ("Please select option number: 8", INPUT),
    ("Adding new host, network or range from the xlsx", DIM),
    ("DC1 has been added to FMC.", OK),
    ("DC2 has been added to FMC.", OK),
    ("… 5 more objects added", DIM),
    ("", TEXT),

    ("Please select option number: 9", INPUT),
    ("Adding new network group from the xlsx", DIM),
    ("PRINTER-01, PRINTER-02 has been added to PRINTERS", OK),
    ("", TEXT),

    ("Please select option number: 10", INPUT),
    ("Following access rule has been added:", TEXT),
    ("", TEXT),
    ("Category name: ACTIVE_DIRECTORY", TEXT),
    ("Access rule: DC-DC", TEXT),
    ("Action: ALLOW", ACCENT),
    ("Source zone: Zone_Inside", TEXT),
    ("Destination zone: Zone_Inside", TEXT),
    ("Port: AD_PORTS", TEXT),
    ("… 3 more rules added (CLIENTS-TO-DC, CLIENTS-TO-WEB, PING-PRINTERS)", DIM),
    ("", TEXT),

    ("Please select option number: 11", INPUT),
    ("ACP available in the domain: ", TEXT),
    ("    Name:  Example_ACP", TEXT),
    ("Enter the ACP Name to export (or press Enter for all): ", TEXT),
    ("Writing rule #1 to CSV...", DIM),
    ("Writing rule #2 to CSV...", DIM),
    ("… 2 more rules written", DIM),
    ("File is at: ./Example_ACP.csv", OK),
    ("", TEXT),

    ("Please select option number: 12", INPUT),
    ("Exporting FMC configuration to the xlsx", DIM),
    ("ACP: 4 exported", TEXT),
    ("SecurityZones: 3 exported", TEXT),
    ("HostNetwork: 7 exported", TEXT),
    ("File is at: ./fmc-export-fmc.example.com-20261027-120000.xlsx", OK),
    ("", TEXT),

    ("Please select option number: 13", INPUT),
    ("FTD-1 ID: id-FTD-1", TEXT),
    ("FTD-2 ID: id-FTD-2", TEXT),
    ("Checking pending FMC changes", DIM),
    ("FMC has no pending changes", TEXT),
    ("Do you want to proceed (Y/N): Y", INPUT),
    ("Adding HA to the FMC", DIM),
    ("High Availability has been created in FMC.", OK),
    ("", TEXT),

    ("Please select option number: 14", INPUT),
    ("Adding EtherChannel", DIM),
    ("FTD-1 ID: id-FTD-1", TEXT),
    ("Port channel has been created in FMC.", OK),
    ("", TEXT),

    ("Please select option number: 15", INPUT),
    ("Adding Subinterfaces", DIM),
    ("Subinterface Port-channel1.10 (VLAN10) has been created in FMC.", OK),
    ("Subinterface Port-channel1.20 (VLAN20) has been created in FMC.", OK),
    ("", TEXT),

    ("Please select option number: 16", INPUT),
    ("$ ", PROMPT),
]


def render_frame(visible_lines, cursor_on):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, WIDTH, TOP_BAR_H], fill=BAR_BG)
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = 20 + i * 22
        draw.ellipse([cx, TOP_BAR_H // 2 - 6, cx + 12, TOP_BAR_H // 2 + 6], fill=color)
    title = "bash — fmc-setup"
    tw = draw.textlength(title, font=font)
    draw.text(((WIDTH - tw) / 2, 9), title, font=font, fill=(200, 200, 200))

    y = TEXT_TOP
    for idx, (text, color) in enumerate(visible_lines):
        is_last = idx == len(visible_lines) - 1
        draw.text((MARGIN_X, y), text, font=font, fill=color)
        if is_last and cursor_on:
            tw = draw.textlength(text, font=font)
            draw.rectangle([MARGIN_X + tw + 3, y + 2, MARGIN_X + tw + 11, y + LINE_HEIGHT - 4], fill=TEXT)
        y += LINE_HEIGHT
    return img


def build_frames():
    frames, durations = [], []
    for i in range(1, len(LINES) + 1):
        visible = LINES[max(0, i - MAX_VISIBLE):i]
        line_text = LINES[i - 1][0]
        is_prompt_line = line_text.startswith("Please select option number")
        is_blank = line_text == ""
        frames.append(render_frame(visible, cursor_on=True))
        durations.append(50 if is_blank else (100 if not is_prompt_line else 180))
        if is_prompt_line:
            # brief "thinking" pause with blinking cursor before the next menu action
            for blink in range(2):
                frames.append(render_frame(visible, cursor_on=(blink % 2 == 0)))
                durations.append(220)

    # hold the final, fully populated frame
    final_visible = LINES[-MAX_VISIBLE:]
    for blink in range(3):
        frames.append(render_frame(final_visible, cursor_on=(blink % 2 == 0)))
        durations.append(500)
    return frames, durations


def main():
    frames, durations = build_frames()
    out = Path(__file__).parent / "demo.gif"
    frames[0].save(
        out, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True,
    )
    print(f"Saved {out} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
