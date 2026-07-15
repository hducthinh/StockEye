import json
import chess
import chess.engine
import os

class ChessEngine:
    def __init__(self, engine_path="engine/stockfish-windows-x86-64-avx2.exe", config_path="config.json"):
        # Nạp cấu hình từ file json
        self.config = {
            "threads": 2,
            "uci_limit_strength": False,
            "uci_elo": 1500,
            "time_limit": 0.5
        }
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    self.config.update(user_config)
            except Exception as e:
                print(f"[Config] Lỗi đọc file {config_path}: {e}")

        self.board = chess.Board() # Khởi tạo bàn cờ ở trạng thái bắt đầu (thế chuẩn)
        self.white_moves = []
        self.black_moves = []
        
        # Đường dẫn tuyệt đối hoặc tương đối tới Stockfish
        if not os.path.exists(engine_path):
            print(f"[Engine] CẢNH BÁO: Không tìm thấy Stockfish tại {engine_path}")
            self.engine = None
        else:
            print("[Engine] Đang khởi động Stockfish...")
            self.engine = chess.engine.SimpleEngine.popen_uci(engine_path)
            
            # Cấu hình Stockfish từ config.json
            self.apply_config_to_engine()
            
    def apply_config_to_engine(self):
        if not self.engine:
            return
            
        engine_options = {"Threads": self.config["threads"]}
        if self.config.get("uci_limit_strength"):
            engine_options["UCI_LimitStrength"] = True
            engine_options["UCI_Elo"] = max(1320, self.config["uci_elo"])
        else:
            engine_options["UCI_LimitStrength"] = False
            
        self.engine.configure(engine_options)
        
        elo_text = self.config['uci_elo'] if self.config.get('uci_limit_strength') else 'Max'
        print(f"[Engine] Cấu hình Stockfish hiện tại: (Elo: {elo_text}, Độ chính xác: {self.config['time_limit']}s)")

    def reload_config(self):
        """Đọc lại cấu hình từ file và áp dụng ngay lập tức"""
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    self.config.update(user_config)
            except Exception as e:
                print(f"[Config] Lỗi đọc file {config_path}: {e}")
                return
                
        self.apply_config_to_engine()

    def reset_board(self):
        self.board.reset()
        self.white_moves = []
        self.black_moves = []

    def is_potential_hover_cancel(self, changed_squares):
        """Kiểm tra logic xem có phải người dùng thả quân về chỗ cũ không"""
        if not self.board.move_stack:
            return False
            
        last_move = self.board.move_stack[-1]
        from_sq = chess.square_name(last_move.from_square)
        to_sq = chess.square_name(last_move.to_square)
        
        if from_sq in changed_squares and to_sq in changed_squares:
            return True
        return False
        
    def undo_last_move(self):
        if not self.board.move_stack:
            return None
        popped = self.board.pop()
        if self.board.turn == chess.WHITE:
            if self.white_moves: self.white_moves.pop()
        else:
            if self.black_moves: self.black_moves.pop()
        return popped

    def _get_net_changes(self, orig_board, seq):
        test_board = orig_board.copy()
        for m in seq:
            test_board.push(m)
            
        net_changed = set()
        for sq in chess.SQUARES:
            if orig_board.piece_at(sq) != test_board.piece_at(sq):
                net_changed.add(chess.square_name(sq))
        return net_changed

    def _find_best_sequence(self, changed_squares, max_depth=2):
        best_seq = []
        best_score = -9999
        changed_list = list(changed_squares)
        orig_board = self.board
        
        last_move = self.board.move_stack[-1] if self.board.move_stack else None
        last_move_from = chess.square_name(last_move.from_square) if last_move else None
        last_move_to = chess.square_name(last_move.to_square) if last_move else None
        
        last_white = self.white_moves[-1] if self.white_moves else None
        last_black = self.black_moves[-1] if self.black_moves else None
        


        def dfs(current_board, depth, current_seq):
            nonlocal best_seq, best_score
            
            if depth > 0:
                net = self._get_net_changes(orig_board, current_seq)
                intersect = len(net.intersection(set(changed_list)))
                
                # Bắt buộc chuỗi nước đi phải giải thích được ít nhất 2 ô bị thay đổi!
                # (Vì một nước đi thực tế luôn làm thay đổi ít nhất ô đi và ô đến)
                # Nếu chỉ khớp 1 ô, đó 99% là bóng mờ/residue fading.
                if intersect >= 2:
                    score = 0
                    n = len(changed_list)
                    
                    # 1. Điểm thưởng cho các ô khớp & Phạt ô không có thực
                    for sq in net:
                        if sq in changed_list:
                            # [SỬA LỖI ĐI NHANH] Không thưởng điểm cho các ô thuộc tàn dư của nước đi trước.
                            # Điều này ngăn DFS ảo tưởng rằng dư âm hoạt ảnh là một nước đi quay lui (reverse move).
                            if sq == last_move_from or sq == last_move_to:
                                pass # Thưởng 0 điểm (Vì đằng nào nó cũng được tha thứ ở bước dưới)
                            else:
                                weight = n - changed_list.index(sq)
                                score += (weight * 10) + 1000
                        else:
                            score -= 3000 # Phạt cực nặng nếu sinh ra ô không có thực
                            
                    # 2. Phạt nếu bỏ sót ô thực tế (unexplained squares)
                    for sq in changed_list:
                        if sq not in net:
                            # KHÔNG PHẠT nếu ô đó là dư âm hoạt ảnh của nước đi ngay trước đó!
                            # Khi highlight của nước đi trước biến mất, nó tạo ra sự thay đổi màu sắc.
                            if sq == last_move_from or sq == last_move_to:
                                continue
                            # [Sửa lỗi] Giảm mức phạt từ 1000 xuống 600
                            score -= 600
                            
                    # 3. Phạt độ dài chuỗi (tránh DFS cố tình nối dài chuỗi để farm điểm trên ô fading)
                    # Một ô khớp được ~1000 điểm. Phạt 1200 điểm/nước đi sẽ đảm bảo:
                    # - 1 nước đi thực sự (khớp 2 ô = 2000đ) -> 2000 - 1200 = 800đ (Lãi)
                    # - 1 nước đi ảo giác (khớp 1 ô fading = 1000đ) -> 1000 - 1200 = -200đ (Lỗ)
                    score -= len(current_seq) * 1200
                    
                    if score > best_score:
                        best_score = score
                        best_seq = list(current_seq)
                    elif score == best_score:
                        if len(current_seq) < len(best_seq):
                            best_seq = list(current_seq)
                        
            if depth == max_depth:
                return
                
            for move in current_board.legal_moves:
                # [SỬA LỖI] Chống ảo giác: Chỉ áp dụng chặn quay lui đối với các nước Premove (trong current_seq).
                # Không so sánh với lịch sử ván cờ, vì đi lùi/ăn lại quân là hợp lệ!
                if len(current_seq) >= 2:
                    prev_premove = current_seq[-2]
                    if move.from_square == prev_premove.to_square and move.to_square == prev_premove.from_square:
                        continue
                        
                from_sq = chess.square_name(move.from_square)
                to_sq = chess.square_name(move.to_square)
                
                # Pruning: Chỉ duyệt các nước đi liên quan đến những ô bị thay đổi
                if from_sq in changed_list or to_sq in changed_list:
                    current_board.push(move)
                    current_seq.append(move)
                    dfs(current_board, depth + 1, current_seq)
                    current_seq.pop()
                    current_board.pop()
                    
        dfs(orig_board.copy(), 0, [])
        
        # Chấp nhận mức điểm > -500 để cho phép sai số 1 ô bị nhiễu (hover noise = -1000)
        # Ví dụ 1 nước đi hợp lệ + 1 ô nhiễu: Lãi 800 - Nhiễu 1000 = -200 > -500 (Được chấp nhận)
        if best_score > -500:
            return best_seq
        return []

    def infer_and_push_move(self, changed_squares):
        """Trúng thưởng thuật toán DFS 2-ply search siêu việt"""
        pushed_moves = []
        best_seq = self._find_best_sequence(changed_squares)
        
        for move in best_seq:
            if self.board.turn == chess.WHITE:
                self.white_moves.append(move)
            else:
                self.black_moves.append(move)
                
            self.board.push(move)
            pushed_moves.append(move.uci())
            print(f"[Engine] Đã cập nhật nước đi: {move.uci()}")
            
        return pushed_moves

    def get_top_moves(self, limit=3):
        """Lấy danh sách Top N nước đi tốt nhất từ Stockfish"""
        if not self.engine:
            return []
            
        import random
        human_error_rate = self.config.get("human_error_rate", 0.0)
        is_human_error = random.random() < human_error_rate
        
        # Lấy dư ra 1 nước nếu có kích hoạt Human Error
        search_limit = limit + 1 if is_human_error else limit
            
        try:
            if self.config.get("uci_limit_strength"):
                top_moves = []
                banned_moves = set()
                
                # Vòng lặp liên tục gọi hàm play() để lấy ra N nước đi theo chuẩn Elo
                for _ in range(search_limit):
                    legal_moves = [m for m in self.board.legal_moves if m not in banned_moves]
                    if not legal_moves:
                        break
                        
                    result = self.engine.play(self.board, chess.engine.Limit(time=self.config["time_limit"]), root_moves=legal_moves, info=chess.engine.INFO_ALL)
                    if not result.move:
                        break
                        
                    score_str = "Elo " + str(self.config["uci_elo"])
                    if result.info and "score" in result.info:
                        score_obj = result.info["score"].white()
                        if score_obj.is_mate():
                            score_str = f"M{score_obj.mate()}"
                        else:
                            val = score_obj.score() / 100.0
                            score_str = f"+{val:.2f}" if val > 0 else f"{val:.2f}"
                            
                    top_moves.append({"move": result.move.uci(), "score": score_str})
                    banned_moves.add(result.move)
                
                # Bỏ qua nước Best nếu giả lập lỗi con người
                if is_human_error and len(top_moves) > 0:
                    top_moves.pop(0)
                    print("[Engine] 🎭 Kích hoạt Human Error: Đang hiển thị nước Inaccuracy thay thế (Elo Mode)!")
                    
                return top_moves[:limit]
            else:
                # Nếu không giới hạn sức mạnh (Max), dùng analyse() để lấy Top nước đi mạnh nhất
                info = self.engine.analyse(
                    self.board, 
                    chess.engine.Limit(time=self.config["time_limit"]), # Giới hạn thời gian suy nghĩ
                    multipv=search_limit
                )
            
                top_moves = []
                for i, entry in enumerate(info):
                    if is_human_error and i == 0:
                        continue # Bỏ qua nước Best hoàn toàn
                        
                    if "pv" in entry:
                        best_move = entry["pv"][0].uci() # pv là list các nước đi tiếp theo (Principal Variation)
                        score_obj = entry["score"].white()
                        
                        # Quy đổi điểm số
                        if score_obj.is_mate():
                            score = f"M{score_obj.mate()}"
                        else:
                            val = score_obj.score() / 100.0
                            score = f"+{val:.2f}" if val > 0 else f"{val:.2f}"
                            
                        top_moves.append({
                            "move": best_move,
                            "score": score
                        })
                        
                    if len(top_moves) >= limit:
                        break
                        
                if is_human_error:
                    print("[Engine] 🎭 Kích hoạt Human Error: Đang hiển thị nước Inaccuracy thay thế!")
                return top_moves
            
        except Exception as e:
            print(f"[Engine] Lỗi phân tích: {e}")
            return []

    def close(self):
        """Đóng an toàn Stockfish khi tắt app"""
        if self.engine:
            self.engine.quit()
