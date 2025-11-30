import pygame
import sys
import time
import json

# File dialogs (for Ctrl+S / Ctrl+L)
import tkinter as tk
from tkinter import filedialog, simpledialog

# Hidden Tk window for dialogs
tk_root = tk.Tk()
tk_root.withdraw()

pygame.init()
FONT = pygame.font.SysFont("consolas", 18)

WIDTH, HEIGHT = 1100, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Astroneer Mission Log Editor")

camera_x = 0
camera_y = 0

# ID system
next_id = 1
free_ids = []

# Save message popup
save_message = ""
save_message_time = 0

# Global clipboard for Editor copy/paste
clipboard = ""

# Currently-selected ID for arrow-key moving (0 = none)
moving_id = 0


# =====================================================================
# FILE DIALOG SAVE
# =====================================================================
def save_file_dialog():
    global save_message, save_message_time

    filepath = filedialog.asksaveasfilename(
        defaultextension=".anrmt",
        filetypes=[("Astroneer Save Mission Tree", "*.anrmt"), ("All Files", "*.*")]
    )
    if not filepath:
        return

    data = []
    for m in missions:
        data.append({
            "id": m.id,
            "x": m.x,
            "y": m.y,
            "text": m.text,
            "type": m.type,
            "color": m.color,
            "logic": m.logic,
            "dependencies": [d.id for d in m.dependencies],
            "mission": {
                "desc": m.mission.get("desc", ""),
                "task": m.mission.get("task", ""),
                "item": m.mission.get("item", ""),
                "rwrd": m.mission.get("rwrd", "")
            }
        })

    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)

    save_message = "Saved!"
    save_message_time = time.time()


# =====================================================================
# FILE DIALOG LOAD
# =====================================================================
def load_file_dialog():
    global next_id, free_ids, camera_x, camera_y

    filepath = filedialog.askopenfilename(
        filetypes=[("Astroneer Mission Tree", "*.anrmt"), ("All Files", "*.*")]
    )
    if not filepath:
        return

    with open(filepath, "r") as f:
        data = json.load(f)

    missions.clear()
    free_ids.clear()
    next_id = 1

    id_map = {}

    # Create missions
    for m in data:
        mid = m["id"]
        new_m = Mission(m["x"], m["y"], mid)
        new_m.text = m["text"]
        new_m.type = m["type"]
        new_m.color = m["color"]
        new_m.logic = m.get("logic", "AND")
        mission_block = m.get("mission", {})
        new_m.mission["desc"] = mission_block.get("desc", "")
        new_m.mission["task"] = mission_block.get("task", "")
        new_m.mission["item"] = mission_block.get("item", "")
        new_m.mission["rwrd"] = mission_block.get("rwrd", "")      # Load extra mission data (if present)

        missions.append(new_m)
        id_map[mid] = new_m

        next_id = max(next_id, mid + 1)

    # Reconstruct dependencies
    for m in data:
        mission_obj = id_map[m["id"]]
        for dep in m["dependencies"]:
            if dep in id_map:
                mission_obj.dependencies.append(id_map[dep])
                id_map[dep].dependents.append(mission_obj)
    
    camera_x = 0
    camera_y = 0


# =====================================================================
# MISSION CLASS
# =====================================================================
class Mission:
    FONT = pygame.font.SysFont("consolas", 20)  # create once per class

    def __init__(self, x, y, mid):
        self.id = mid
        self.x = x
        self.y = y
        self.text = f"Mission {mid}"
        self.type = "normal"
        self.color = "#3FA9F5"
        self.logic = "AND"
        self.checked = False
        self.dependencies = []
        self.dependents = []
        self.rect = pygame.Rect(self.x, self.y, 180, 60)
        self.mission = {
            "desc": "",
            "task": "",
            "item": "",
            "rwrd": ""
        }

    def contains(self, pos):
        px, py = pos
        return self.rect.collidepoint(px - camera_x, py - camera_y)

    def wrap_text(self, text, font, max_width):
        """Simple word-wrapping helper."""
        words = text.split(" ")
        lines = []
        current = ""
        for w in words:
            test = f"{current} {w}".strip()
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
        return lines

    def draw(self, surf):
        draw_rect = self.rect.move(camera_x, camera_y)
        bg_color = (170, 170, 170) if self.type == "special" else pygame.Color(self.color)

        pygame.draw.rect(surf, bg_color, draw_rect, border_radius=10)
        pygame.draw.rect(surf, (0, 0, 0), draw_rect, 2, border_radius=10)

        # Checkmark
        if self.checked:
            check = self.FONT.render("+", True, (0, 150, 0))
            surf.blit(check, (draw_rect.right - 20, draw_rect.bottom - 25))

        # Text wrapping
        max_width = self.rect.width - 10
        lines = self.wrap_text(self.text, self.FONT, max_width)

        # Dynamic height
        line_h = 20
        top_pad = 10
        bottom_pad = 40
        needed_height = top_pad + len(lines) * line_h + bottom_pad
        if needed_height > self.rect.height:
            self.rect.height = needed_height
            draw_rect.height = needed_height

        y_offset = draw_rect.y + 5
        for line in lines:
            txt = self.FONT.render(line, True, (0, 0, 0))
            surf.blit(txt, (draw_rect.x + 5, y_offset))
            y_offset += line_h

        # Type + logic tag
        logic_text = f" | {self.logic}" if len(self.dependencies) > 1 else ""
        tag = self.FONT.render(f"{self.type}{logic_text}", True, (30, 30, 30))
        surf.blit(tag, (draw_rect.x + 5, draw_rect.bottom - 22))


# =====================================================================
# EDITOR POPUP
# =====================================================================
class Editor:
    def __init__(self, mission):
        self.m = mission
        self.active = True

        self.text_buffer = mission.text
        self.color_buffer = mission.color
        self.type_buffer = mission.type
        self.logic_buffer = mission.logic
        self.deps_buffer = ",".join(str(d.id) for d in mission.dependencies)

        self.fields = ["name", "type", "color", "logic", "deps"]
        self.current_field = 0

    def draw(self, surf):
        pygame.draw.rect(surf, (40, 40, 40), (150, 100, 800, 500))
        pygame.draw.rect(surf, (200, 200, 200), (150, 100, 800, 500), 3)

        lines = [
            f"Editing Mission ID: {self.m.id}",
            "",
            f"Name: {self.text_buffer}",
            f"Type (normal/special): {self.type_buffer}",
            f"Color (hex): {self.color_buffer}",
            f"Logic (AND/OR): {self.logic_buffer}",
            f"Dependencies (IDs): {self.deps_buffer}",
            "",
            "TAB = switch field",
            "ENTER = save changes",
            "T = toggle AND/OR",
            "Ctrl+C = copy field",
            "Ctrl+V = paste field",
            "P = move by ID (also works from main view)"
        ]

        y = 120
        for i, line in enumerate(lines):
            highlight_row = 2 + self.current_field
            color = (255, 255, 0) if i == highlight_row else (230, 230, 230)
            txt = FONT.render(line, True, color)
            surf.blit(txt, (170, y))
            y += 30

    def handle_event(self, e):
        global clipboard

        if e.type != pygame.KEYDOWN:
            return

        # ---- COPY (Ctrl+C) ----
        if e.key == pygame.K_c and pygame.key.get_mods() & pygame.KMOD_CTRL:
            field = self.fields[self.current_field]

            if field == "name":
                clipboard = self.text_buffer
            elif field == "type":
                clipboard = self.type_buffer
            elif field == "color":
                clipboard = self.color_buffer
            elif field == "logic":
                clipboard = self.logic_buffer
            elif field == "deps":
                clipboard = self.deps_buffer
            return

        # ---- PASTE (Ctrl+V) ----
        if e.key == pygame.K_v and pygame.key.get_mods() & pygame.KMOD_CTRL:
            field = self.fields[self.current_field]

            if field == "name":
                self.text_buffer = clipboard

            elif field == "type":
                # only allow "normal" or "special"
                if isinstance(clipboard, str) and clipboard.lower() in ("normal", "special"):
                    self.type_buffer = clipboard.lower()

            elif field == "color":
                if isinstance(clipboard, str):
                    self.color_buffer = clipboard

            elif field == "logic":
                if isinstance(clipboard, str) and clipboard.upper() in ("AND", "OR"):
                    self.logic_buffer = clipboard.upper()

            elif field == "deps":
                if isinstance(clipboard, str):
                    self.deps_buffer = clipboard

            return

        # Toggle AND/OR (only active when logic field is selected)
        if e.key == pygame.K_t and self.current_field == 3:
            self.logic_buffer = "OR" if self.logic_buffer == "AND" else "AND"
            return

        if e.key == pygame.K_TAB:
            self.current_field = (self.current_field + 1) % len(self.fields)
            return

        if e.key == pygame.K_RETURN:
            # Save data back to mission
            self.m.text = self.text_buffer
            self.m.type = self.type_buffer
            self.m.color = self.color_buffer
            self.m.logic = self.logic_buffer

            self.m.dependencies.clear()
            ids = [s.strip() for s in self.deps_buffer.split(",") if s.strip().isdigit()]
            for d in ids:
                did = int(d)
                for m in missions:
                    if m.id == did:
                        self.m.dependencies.append(m)
                        m.dependents.append(self.m)

            self.active = False
            return

        # Typing into fields
        field = self.fields[self.current_field]

        if field == "name":
            if e.key == pygame.K_BACKSPACE:
                self.text_buffer = self.text_buffer[:-1]
            else:
                self.text_buffer += e.unicode

        elif field == "type":
            if e.key == pygame.K_BACKSPACE:
                self.type_buffer = "normal"
            else:
                if e.unicode.lower() in ["n", "s"]:
                    self.type_buffer = "normal" if e.unicode.lower() == "n" else "special"

        elif field == "color":
            if e.key == pygame.K_BACKSPACE:
                self.color_buffer = self.color_buffer[:-1]
            else:
                self.color_buffer += e.unicode

        elif field == "logic":
            # typing disabled, toggle only
            pass

        elif field == "deps":
            if e.key == pygame.K_BACKSPACE:
                self.deps_buffer = self.deps_buffer[:-1]
            else:
                self.deps_buffer += e.unicode


# =====================================================================
# TRIANGLE DRAWING (fixed rotation)
# =====================================================================
import math


def draw_rotated_triangle(surface, center, angle, size, color):
    half = size / 2

    points = [
        (0, -half),
        (-half, half),
        (half, half),
    ]

    rad = math.radians(angle)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    rotated = []
    for x, y in points:
        rx = x * cos_a - y * sin_a
        ry = x * sin_a + y * cos_a
        rotated.append((center[0] + rx, center[1] + ry))

    pygame.draw.polygon(surface, color, rotated)


def draw_triangle_line(surface, start, end, color=(0, 0, 0), size=10, spacing=6):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.hypot(dx, dy)
    if dist == 0:
        return

    ux = dx / dist
    uy = dy / dist

    angle = math.degrees(math.atan2(dy, dx)) - 90

    step = size + spacing
    steps = int(dist // step)

    for i in range(steps):
        cx = start[0] + ux * i * step
        cy = start[1] + uy * i * step
        draw_rotated_triangle(surface, (cx, cy), angle, size, color)


# =====================================================================
# MAIN DRAW — dependency lines
# =====================================================================
def draw_links():
    for m in missions:
        for d in m.dependencies:
            start = ((m.rect.centerx + camera_x), (m.rect.centery + camera_y))
            end = ((d.rect.centerx + camera_x), (d.rect.centery + camera_y))
            draw_triangle_line(screen, start, end, color=(0, 0, 0), size=10, spacing=6)

def open_mission_popup(mission):
    popup = tk.Toplevel()
    popup.title(f"Edit Mission {mission.id} Details")
    popup.geometry("600x850")  # extra space for instructions

    # === Description ===
    tk.Label(popup, text="Mission Description:").pack(anchor="w", padx=10, pady=(10, 0))
    desc_box = tk.Text(popup, height=8)
    desc_box.pack(fill="x", padx=10)
    desc_box.insert("1.0", mission.mission.get("desc", ""))

    # === Tasks ===
    tk.Label(popup, text="Mission Tasks:").pack(anchor="w", padx=10, pady=(10, 0))
    task_box = tk.Text(popup, height=4)
    task_box.pack(fill="x", padx=10)
    task_box.insert("1.0", mission.mission.get("task", ""))

    # === Item ===
    tk.Label(popup, text="Mission Item:").pack(anchor="w", padx=10, pady=(10, 0))
    item_box = tk.Text(popup, height=2)
    item_box.pack(fill="x", padx=10)
    item_box.insert("1.0", mission.mission.get("item", ""))

    # === Reward ===
    tk.Label(popup, text="Mission Reward:").pack(anchor="w", padx=10, pady=(10, 0))
    rwrd_box = tk.Text(popup, height=4)
    rwrd_box.pack(fill="x", padx=10)
    rwrd_box.insert("1.0", mission.mission.get("rwrd", ""))

    # === Save + Close ===
    def save_and_close():
        mission.mission["desc"] = desc_box.get("1.0", "end").strip()
        mission.mission["task"] = task_box.get("1.0", "end").strip()
        mission.mission["item"] = item_box.get("1.0", "end").strip()
        mission.mission["rwrd"] = rwrd_box.get("1.0", "end").strip()
        popup.destroy()

    tk.Button(popup, text="Save", command=save_and_close).pack(pady=10)

    # === Instructions below Save button ===
    instructions = (
        "Format for Mission Tasks (example):\n"
        "(name1,count1,task1),(name2,count2,task2)\n\n"
        "Format for Mission Rewards (example):\n"
        "(type1,count1,rew1),(type2,count2,rew2)\n\n"
        "Mission Item can either be an item, or nothing.\n"
        "If the box is blank, there is no mission item."
    )
    tk.Label(popup, text=instructions, justify="left", anchor="w").pack(anchor="w", padx=10, pady=(50,100))

    # Force window on top
    popup.lift()
    popup.attributes("-topmost", True)
    popup.after(100, lambda: popup.attributes("-topmost", False))

    # 🔥 BLOCK pygame but exit automatically when popup closes
    while popup.winfo_exists():
        popup.update()

# =====================================================================
# MAIN LOOP
# =====================================================================
missions = []
editor = None

clock = pygame.time.Clock()

while True:
    screen.fill((235, 235, 235))

    # Get pressed keys once per frame
    pressed = pygame.key.get_pressed()

    move_speed = 5
    moving_speed = 4

    # If editor isn't open, allow camera WASD movement
    if not (editor and editor.active):
        if pressed[pygame.K_w]:
            camera_y += move_speed
        if pressed[pygame.K_s]:
            camera_y -= move_speed
        if pressed[pygame.K_a]:
            camera_x += move_speed
        if pressed[pygame.K_d]:
            camera_x -= move_speed

    # If moving_id is active (>0), move that mission with arrow keys
    if moving_id:
        target = next((mm for mm in missions if mm.id == moving_id), None)
        if target:
            dx = 0
            dy = 0
            if pressed[pygame.K_UP]:
                dy -= moving_speed
            if pressed[pygame.K_DOWN]:
                dy += moving_speed
            if pressed[pygame.K_LEFT]:
                dx -= moving_speed
            if pressed[pygame.K_RIGHT]:
                dx += moving_speed
            if dx or dy:
                # Update both stored position and rect so saving works
                target.x += dx
                target.y += dy
                target.rect.x = int(target.x)
                target.rect.y = int(target.y)
        else:
            # invalid ID: clear moving_id and notify
            moving_id = 0
            save_message = "Move ID not found — stopped"
            save_message_time = time.time()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.VIDEORESIZE:
            WIDTH, HEIGHT = event.w, event.h
            screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)

        # Ctrl+S save and Ctrl+L load and P popup handling
        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            if event.key == pygame.K_s and mods & pygame.KMOD_CTRL:
                save_file_dialog()

            if event.key == pygame.K_l and mods & pygame.KMOD_CTRL:
                load_file_dialog()

            # Press P to open a popup to enter ID to move (0 = stop moving)
            if event.key == pygame.K_p and not(editor and editor.active):
                try:
                    val = simpledialog.askinteger("Move Mission", "Enter mission ID (0 to exit):", parent=tk_root, minvalue=0)
                    # askinteger returns None if cancelled
                    if val is None:
                        # cancelled, do nothing
                        pass
                    else:
                        moving_id = int(val)
                        if moving_id == 0:
                            save_message = "Move mode exited"
                        else:
                            # if id not found warn user
                            if not any(mm.id == moving_id for mm in missions):
                                save_message = f"ID {moving_id} not found"
                                moving_id = 0
                            else:
                                save_message = f"Moving mission ID {moving_id} (use arrows)"
                        save_message_time = time.time()
                except Exception as ex:
                    save_message = f"Error: {ex}"
                    save_message_time = time.time()
            
            # Q = open mission popup for the selected ID
            if event.key == pygame.K_q and not (editor and editor.active):
                if moving_id != 0:
                    # find that mission object
                    target = next((mm for mm in missions if mm.id == moving_id), None)
                    if target: open_mission_popup(target)
                    else: print("No mission with that ID exists.")
                else: print("No mission ID selected. Press P to select one.")


            # Ctrl+N - create a fresh mission tree (wipe everything)
            if event.key == pygame.K_n and mods & pygame.KMOD_CTRL:
                missions.clear()
                free_ids.clear()
                camera_x = 0
                camera_y = 0
                next_id = 1     # reset ID counter back to 1 (or whatever your base is)
                moving_id = 0
                editor = None

        # When editor is active, forward events to the editor only
        if editor and editor.active:
            editor.handle_event(event)
            continue
        else:
            editor = None

        # Right-click delete
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            mx, my = event.pos
            to_delete = None

            for m in missions:
                if m.contains((mx, my)):
                    to_delete = m
                    break

            if to_delete:
                for other in missions:
                    if to_delete in other.dependencies:
                        other.dependencies.remove(to_delete)
                    if to_delete in other.dependents:
                        other.dependents.remove(to_delete)

                missions.remove(to_delete)
                free_ids.append(to_delete.id)
                free_ids.sort()
                continue

        # Left click create/edit
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            clicked = None
            for m in missions:
                if m.contains((mx, my)):
                    clicked = m
                    break

            if clicked:
                editor = Editor(clicked)
            else:
                if free_ids:
                    mid = free_ids.pop(0)
                else:
                    mid = next_id
                    next_id += 1

                new_m = Mission(mx - camera_x - 90, my - camera_y - 30, mid)
                # ensure internal x/y and rect agree
                new_m.x = float(new_m.rect.x)
                new_m.y = float(new_m.rect.y)
                missions.append(new_m)

        # Toggle checkmark (E)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
            mx, my = pygame.mouse.get_pos()
            for m in missions:
                if m.contains((mx, my)):
                    m.checked = not m.checked
                    break

    draw_links()

    for m in missions:
        m.draw(screen)

    if editor:
        editor.draw(screen)

    # show save/mode messages briefly
    if save_message and time.time() - save_message_time < 2:
        msg = FONT.render(save_message, True, (0, 0, 0))
        screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, 20))
    else:
        save_message = ""

    try:
        tk_root.update()
    except:
        pass

    pygame.display.flip()
    clock.tick(60)
