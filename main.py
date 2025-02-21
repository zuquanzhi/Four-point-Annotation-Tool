import pygame
import sys
import os
import numpy as np
import cv2
import tkinter as tk
from tkinter import filedialog, simpledialog, colorchooser
import copy
import json
import hashlib

# Initialize Pygame
pygame.init()

class Button:
    def __init__(self, rect, text, color, hover_color):
        self.rect = rect
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.current_color = color
        self.font = pygame.font.Font(None, 36)
        self.hover = False

    def draw(self, screen):
        pygame.draw.rect(screen, self.current_color, self.rect, border_radius=5)
        text_surf = self.font.render(self.text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def check_hover(self, mouse_pos):
        self.hover = self.rect.collidepoint(mouse_pos)
        self.current_color = self.hover_color if self.hover else self.color

class AnnotationApp:
    def __init__(self):
        # Window settings
        self.screen_width = 1600
        self.screen_height = 900
        self.image_panel_width = 1200
        self.control_panel_width = 400
        
        self.screen = None
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Image related
        self.image = None
        self.image_scale = 1.0
        self.image_offset = (0, 0)
        self.original_image = None
        self.current_file = ""
        self.image_files = []
        self.current_index = 0
        
        # Annotation related
        self.annotations = []
        self.history = []
        self.selected_point = (-1, -1)
        self.max_points = 4
        self.class_id = 0
        self.id_colors = {}
        self.load_id_colors()
        
        # UI elements
        self.font = pygame.font.Font(None, 36)
        self.title_font = pygame.font.Font(None, 24)
        self.control_bg = (60, 60, 60)
        self.save_directory = None
        
        # Control panel
        control_x = self.image_panel_width + 20
        self.buttons = [
            Button(pygame.Rect(control_x, 50, 360, 50), 
                  "Save (Enter)", (0, 150, 0), (0, 200, 0)),
            Button(pygame.Rect(control_x, 120, 360, 50),
                  "Skip (->)", (150, 0, 0), (200, 0, 0)),
            Button(pygame.Rect(control_x, 190, 360, 50),
                  "Undo (Ctrl+Z)", (100, 100, 100), (150, 150, 150)),
            Button(pygame.Rect(control_x, 260, 360, 50),
                  "Delete Selected (Del)", (200, 50, 50), (250, 100, 100)),
            Button(pygame.Rect(control_x, 330, 360, 50),
                  "Set Current ID", (80, 80, 180), (120, 120, 220)),
            # Button(pygame.Rect(control_x, 400, 360, 50),
            #       "Edit ID Color", (80, 180, 80), (120, 220, 120))
        ]
        
        # 输入框
        self.input_box = pygame.Rect(control_x, 460, 360, 40)
        self.input_text = ""
        self.input_active = False
        
        # Status
        self.status_msg = ""

    def get_color_for_id(self, class_id):
        """自动生成或获取预设颜色"""
        if class_id in self.id_colors:
            return self.id_colors[class_id]
        
        # 生成唯一颜色
        h = hashlib.md5(str(class_id).encode()).hexdigest()
        color = (
            int(h[0:2], 16) % 200 + 50,
            int(h[2:4], 16) % 200 + 50,
            int(h[4:6], 16) % 200 + 50
        )
        self.id_colors[class_id] = color
        return color

    def load_id_colors(self):
        """加载颜色预设"""
        try:
            with open("id_colors.json", "r") as f:
                self.id_colors = json.load(f)
                self.id_colors = {int(k): tuple(v) for k,v in self.id_colors.items()}
        except:
            self.id_colors = {}

    def save_id_colors(self):
        """保存颜色预设"""
        with open("id_colors.json", "w") as f:
            json.dump(self.id_colors, f)

    def load_images_from_folder(self, folder_path):
        self.image_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
                          if f.lower().endswith(('png', 'jpg', 'jpeg', 'bmp'))]
        if not self.image_files:
            print(f"No images found in {folder_path}")
            self.running = False

    def load_image(self, file_path):
        if not os.path.exists(file_path):
            print(f"Error: Image {file_path} not found!")
            return self.skip_to_next_image()

        self.current_file = file_path
        self.original_image = cv2.imread(file_path)
        
        if self.original_image is None:
            print(f"Error: Failed to read {file_path}")
            return self.skip_to_next_image()

        self.original_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)
        self.image = pygame.surfarray.make_surface(
            np.transpose(self.original_image, (1, 0, 2))
        )
        self.status_msg = f"Image {self.current_index+1}/{len(self.image_files)}"
        self.fit_image_to_screen()

    def fit_image_to_screen(self):        
        img_h, img_w = self.original_image.shape[:2]
        scale_w = (self.image_panel_width - 40) / img_w
        scale_h = (self.screen_height - 40) / img_h
        self.image_scale = min(scale_w, scale_h)
        
        scaled_w = int(img_w * self.image_scale)
        scaled_h = int(img_h * self.image_scale)
        self.image_offset = (
            (self.image_panel_width - scaled_w) // 2,
            (self.screen_height - scaled_h) // 2
        )
        
        scaled_image = pygame.transform.scale(self.image, (scaled_w, scaled_h))
        self.image = scaled_image

    def update_display(self):
        self.screen.fill((40, 40, 40))
        
        # Draw image area
        if self.image:
            self.screen.blit(self.image, self.image_offset)
            
            # Draw annotations
            for ann in self.annotations:
                points = self.scale_points(ann['points'], to_screen=True)
                color = self.get_color_for_id(ann['id'])
                if ann.get('selected'):
                    color = tuple(min(c+50, 255) for c in color)
                
                if len(points) >= 8:
                    # Draw quadrilateral
                    pygame.draw.lines(self.screen, color, True, [
                        (points[0], points[1]),
                        (points[2], points[3]),
                        (points[4], points[5]),
                        (points[6], points[7])
                    ], 3)
                    
                    # Draw class ID
                    center_x = sum(points[::2]) // 4
                    center_y = sum(points[1::2]) // 4
                    id_surf = self.title_font.render(str(ann['id']), True, (255, 255, 0))
                    self.screen.blit(id_surf, (center_x - 10, center_y - 10))
                
                # Draw points
                for i in range(0, len(points), 2):
                    pygame.draw.circle(self.screen, (250, 50, 50), 
                                     (points[i], points[i+1]), 7)

        # Draw control panel
        self.draw_control_panel()
        pygame.display.flip()

    def scale_points(self, points, to_screen=True):
        scaled = []
        offset_x, offset_y = self.image_offset
        scale = self.image_scale if to_screen else 1/self.image_scale
        
        for i in range(0, len(points), 2):
            x = (points[i] * scale) + offset_x if to_screen else (points[i] - offset_x) / scale
            y = (points[i+1] * scale) + offset_y if to_screen else (points[i+1] - offset_y) / scale
            scaled.extend([int(x), int(y)])
            
        return scaled

    def draw_control_panel(self):
        # 控制面板背景
        pygame.draw.rect(self.screen, self.control_bg, 
                        (self.image_panel_width, 0, 
                         self.control_panel_width, self.screen_height))
        
        # 按钮
        for btn in self.buttons:
            btn.draw(self.screen)
            
        # 当前ID显示
        current_id_surf = self.font.render(f"Current ID: {self.class_id}", True, (255,255,255))
        self.screen.blit(current_id_surf, (self.image_panel_width + 20, 470))
        
        # 输入框
        pygame.draw.rect(self.screen, (100,100,200) if self.input_active else (80,80,180), 
                        self.input_box, 0, border_radius=3)
        text_surf = self.font.render(self.input_text, True, (255,255,255))
        self.screen.blit(text_surf, (self.input_box.x + 10, self.input_box.y + 5))
        
        # 状态信息
        status_surf = self.title_font.render(self.status_msg, True, (200,200,200))
        self.screen.blit(status_surf, (self.image_panel_width + 20, self.screen_height - 50))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_mouse_down(event)
                
            elif event.type == pygame.MOUSEMOTION:
                self.handle_mouse_move(event)
                
            elif event.type == pygame.MOUSEBUTTONUP:
                self.selected_point = (-1, -1)
                
            elif event.type == pygame.KEYDOWN:
                self.handle_key_down(event)

    def handle_mouse_down(self, event):
        mouse_pos = event.pos
        
        # 控制面板点击
        if mouse_pos[0] > self.image_panel_width:
            for btn in self.buttons:
                if btn.rect.collidepoint(mouse_pos):
                    if btn.text.startswith("Save"):
                        self.save_annotations()
                    elif btn.text.startswith("Skip"):
                        self.skip_to_next_image()
                    elif btn.text.startswith("Undo"):
                        self.undo()
                    elif btn.text.startswith("Delete"):
                        self.delete_selected()
                    elif btn.text.startswith("Set Current"):
                        self.set_current_id()
                    elif btn.text.startswith("Edit ID"):
                        self.edit_id_color()
                    return
                    
            if self.input_box.collidepoint(mouse_pos):
                self.input_active = True
                self.input_text = str(self.class_id)
            else:
                self.input_active = False
            return
                
        # 图片区域点击
        img_pos = self.screen_to_image_pos(mouse_pos)
        if event.button == 1:  # 左键添加点
            self.add_annotation_point(img_pos)
        elif event.button == 3:  # 右键选择标注
            self.select_annotation(img_pos)

    def set_current_id(self):
        """设置当前ID"""
        try:
            new_id = int(self.input_text)
            self.class_id = new_id
            self.status_msg = f"Current ID set to {new_id}"
        except:
            self.status_msg = "Invalid ID format"

    def edit_id_color(self):
        """编辑ID颜色"""
        root = tk.Tk()
        root.withdraw()
        try:
            target_id = int(self.input_text)
            color = colorchooser.askcolor(title=f"Choose color for ID {target_id}")[0]
            if color:
                self.id_colors[target_id] = tuple(map(int, color[:3]))
                self.save_id_colors()
                self.status_msg = f"Color updated for ID {target_id}"
        except:
            self.status_msg = "Invalid ID format"

    def screen_to_image_pos(self, screen_pos):
        x = (screen_pos[0] - self.image_offset[0]) / self.image_scale
        y = (screen_pos[1] - self.image_offset[1]) / self.image_scale
        return (int(x), int(y))

    def add_annotation_point(self, img_pos):
        if not self.image:
            return

        self.record_history()
        
        if not self.annotations or len(self.annotations[-1]['points']) >= self.max_points*2:
            self.annotations.append({
                'id': self.class_id,
                'points': [],
                'selected': False
            })
            
        self.annotations[-1]['points'].extend(img_pos)
        if len(self.annotations[-1]['points']) == self.max_points*2:
            self.status_msg = "Quadrilateral completed"

    def select_annotation(self, img_pos):
        for ann in self.annotations:
            ann['selected'] = False
            
        for ann in reversed(self.annotations):
            points = ann['points']
            if len(points) < 8:
                continue
                
            if self.point_in_polygon(img_pos, points):
                ann['selected'] = True
                self.class_id = ann['id']
                self.input_text = str(self.class_id)
                self.status_msg = f"Selected ID {self.class_id}"
                return

    def point_in_polygon(self, point, polygon):
        x, y = point
        n = len(polygon)//2
        inside = False
        for i in range(n):
            j = (i + 1) % n
            xi, yi = polygon[2*i], polygon[2*i+1]
            xj, yj = polygon[2*j], polygon[2*j+1]
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
        return inside

    def handle_mouse_move(self, event):
        if self.selected_point != (-1, -1) and event.buttons[0]:
            ann_idx, pt_idx = self.selected_point
            img_pos = self.screen_to_image_pos(event.pos)
            self.annotations[ann_idx]['points'][pt_idx] = img_pos[0]
            self.annotations[ann_idx]['points'][pt_idx+1] = img_pos[1]
            self.update_display()

    def handle_key_down(self, event):
        # 快捷键
        if event.key == pygame.K_RETURN:
            if self.input_active:
                self.set_current_id()
            else:
                self.save_annotations()
        elif event.key == pygame.K_RIGHT:
            self.skip_to_next_image()
        elif event.key == pygame.K_DELETE:
            self.delete_selected()
        elif event.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self.undo()
            
        # 输入处理
        if self.input_active:
            if event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif event.unicode.isdigit():
                self.input_text += event.unicode

    def save_annotations(self):
        if not self.current_file or not self.save_directory:
            return

        base_name = os.path.basename(self.current_file).split('.')[0]
        yolo_path = os.path.join(self.save_directory, f"{base_name}.txt")
        
        with open(yolo_path, 'w') as f:
            img_h, img_w = self.original_image.shape[:2]
            for ann in self.annotations:
                points = ann['points']
                if len(points) != 8:
                    continue
                    
                normalized = [f"{ann['id']}"] + \
                            [f"{p/img_w} {points[i+1]/img_h}" for i, p in enumerate(points[::2])]
                f.write(' '.join(normalized) + '\n')
        
        self.status_msg = f"Saved to {os.path.basename(yolo_path)}"
        self.skip_to_next_image()

    def skip_to_next_image(self):
        if self.current_index < len(self.image_files)-1:
            self.current_index += 1
            self.load_image(self.image_files[self.current_index])
            self.annotations = []
        else:
            self.status_msg = "Last image reached"

    def delete_selected(self):
        self.annotations = [a for a in self.annotations if not a['selected']]
        self.update_display()

    def record_history(self):
        self.history.append(copy.deepcopy(self.annotations))

    def undo(self):
        if self.history:
            self.annotations = self.history.pop()
            self.update_display()
            self.status_msg = "Undo successful"

    def run(self):
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Four-point Annotation Tool")
        
        # 选择文件夹
        root = tk.Tk()
        root.withdraw()
        
        img_folder = filedialog.askdirectory(title="Select Image Folder")
        if not img_folder:
            return
        self.load_images_from_folder(img_folder)
        if not self.image_files:
            return
            
        out_folder = filedialog.askdirectory(title="Select Output Folder")
        if out_folder:
            self.save_directory = out_folder
            os.makedirs(out_folder, exist_ok=True)
            
        self.load_image(self.image_files[0])

        while self.running:
            self.handle_events()
            self.update_display()
            self.clock.tick(60)

        pygame.quit()

if __name__ == '__main__':
    app = AnnotationApp()
    app.run()
