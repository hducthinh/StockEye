import ctypes
import math
import random
import time

class MouseController:
    def __init__(self, capture, worker=None):
        self.capture = capture
        self.worker = worker
        
    def ease_in_out_cubic(self, t):
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - math.pow(-2 * t + 2, 3) / 2

    def generate_bezier_curve(self, p0, p1, p2, p3, steps):
        curve = []
        for i in range(steps + 1):
            t = i / steps if steps > 0 else 1
            t = self.ease_in_out_cubic(t)
            x = (1-t)**3 * p0[0] + 3*(1-t)**2*t * p1[0] + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0]
            y = (1-t)**3 * p0[1] + 3*(1-t)**2*t * p1[1] + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1]
            curve.append((int(x), int(y)))
        return curve

    def human_move_mouse(self, target_x, target_y, duration, curvature_val):
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        start_x, start_y = pt.x, pt.y
        
        p0 = (start_x, start_y)
        p3 = (target_x, target_y)
        dist = math.hypot(target_x - start_x, target_y - start_y)
        
        offset_val = dist * (curvature_val / 100.0)
        p1 = (
            start_x + (target_x - start_x) * 0.3 + random.uniform(-offset_val, offset_val),
            start_y + (target_y - start_y) * 0.3 + random.uniform(-offset_val, offset_val)
        )
        p2 = (
            start_x + (target_x - start_x) * 0.7 + random.uniform(-offset_val, offset_val),
            start_y + (target_y - start_y) * 0.7 + random.uniform(-offset_val, offset_val)
        )
        
        steps = max(5, int(duration * 120))
        curve = self.generate_bezier_curve(p0, p1, p2, p3, steps)
        
        start_time = time.perf_counter()
        for i, (cx, cy) in enumerate(curve):
            ctypes.windll.user32.SetCursorPos(cx, cy)
            target_elapsed = (i / steps) * duration
            while time.perf_counter() - start_time < target_elapsed:
                pass
        ctypes.windll.user32.SetCursorPos(int(target_x), int(target_y))

    def move_and_click(self, px_x, px_y, delay, travel_time, context=None, move=True, click=True):
        if move:
            offset_limit = self.capture.sq_width * 0.15
            rx = px_x + random.uniform(-offset_limit, offset_limit)
            ry = px_y + random.uniform(-offset_limit, offset_limit)
            
            config_data = self.worker.config_data if self.worker else {}
            enable_human = config_data.get("human_mouse", True)
            curvature_val = config_data.get("mouse_curvature", 30)
            
            if not enable_human:
                time.sleep(travel_time)
                ctypes.windll.user32.SetCursorPos(int(rx), int(ry))
            else:
                fullmove = context.get("fullmove_number", 99) if context else 99
                time_left = getattr(self.worker, 'current_time_left', 60.0) if self.worker else 60.0
                apply_overshoot = fullmove < 20 or time_left > 30.0
                
                # Không teleport, chỉ đẩy nhanh tốc độ vẽ
                actual_travel = max(0.005, travel_time)
                
                if apply_overshoot and random.random() < 0.5 and actual_travel > 0.05:
                    os_x = rx + random.uniform(-offset_limit * 1.5, offset_limit * 1.5)
                    os_y = ry + random.uniform(-offset_limit * 1.5, offset_limit * 1.5)
                    self.human_move_mouse(os_x, os_y, actual_travel * 0.8, curvature_val)
                    self.human_move_mouse(rx, ry, actual_travel * 0.2, curvature_val)
                else:
                    self.human_move_mouse(rx, ry, actual_travel, curvature_val)
        
        if click:
            is_scr = context.get("is_scramble", False) if context else False
            ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0) # LEFTDOWN
            # Giữ chuột ít nhất 15ms để trình duyệt kịp ghi nhận event (tránh bị drop)
            time.sleep(0.015 if is_scr else random.uniform(0.02, 0.05))
            ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0) # LEFTUP
            time.sleep(0.015 if is_scr else 0.03)
