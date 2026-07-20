import json
import chess
import chess.engine
import os
import threading

class ChessEngine:
    def __init__(self, engine_path="engine/stockfish-windows-x86-64-avx2.exe", config_path="config.json"):
        self.lock = threading.RLock()
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
        self.analysis_limit = chess.engine.Limit(time=0.1)
        
        # Đường dẫn tuyệt đối hoặc tương đối tới Stockfish
        if not os.path.exists(engine_path):
            print(f"[Engine] CẢNH BÁO: Không tìm thấy Stockfish tại {engine_path}")
            self.engine = None
        else:
            print("[Engine] Đang khởi động Stockfish...")
            self.engine = chess.engine.SimpleEngine.popen_uci(engine_path)
            
            # Load cấu hình Stockfish
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
        """Cập nhật cấu hình tức thì"""
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
        with self.lock:
            self.board.reset()
            self.white_moves = []
            self.black_moves = []
            
    def set_board_fen(self, fen):
        with self.lock:
            self.board.set_fen(fen)
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
        with self.lock:
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
                            # NGOẠI LỆ NHẬP THÀNH: Bỏ qua hình phạt nếu ô thuộc về Xe nhập thành (do chess client thường không highlight Xe)
                            is_castling_rook_sq = False
                            tmp_board = orig_board.copy()
                            for m in current_seq:
                                if tmp_board.is_castling(m):
                                    if tmp_board.turn == chess.WHITE:
                                        if m.to_square == chess.G1 and sq in ['h1', 'f1']: is_castling_rook_sq = True
                                        elif m.to_square == chess.C1 and sq in ['a1', 'd1']: is_castling_rook_sq = True
                                    else:
                                        if m.to_square == chess.G8 and sq in ['h8', 'f8']: is_castling_rook_sq = True
                                        elif m.to_square == chess.C8 and sq in ['a8', 'd8']: is_castling_rook_sq = True
                                tmp_board.push(m)
                                
                            if is_castling_rook_sq:
                                score += 1000 # Thưởng điểm nhập thành
                            else:
                                score -= 3000 # Phạt nặng nếu sai lệch ô cờ
                            
                    # Phạt ô thực tế không giải thích được
                    for sq in changed_list:
                        if sq not in net:
                            # Bỏ qua dư âm hoạt ảnh nước đi trước
                            if sq == last_move_from or sq == last_move_to:
                                continue
                            # Phạt 600đ/ô nhiễu để tránh nhận diện sai
                            score -= 600
                            
                    # Phạt độ dài chuỗi để tránh DFS lạm dụng
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
        with self.lock:
            pushed_moves = []
            best_seq = []
            
            # [TỐI ƯU] Hash Map O(1) Lookup
            if len(changed_squares) == 2:
                legal_moves_map = {}
                for m in self.board.legal_moves:
                    key = f"{chess.square_name(m.from_square)}{chess.square_name(m.to_square)}"
                    if key not in legal_moves_map or m.promotion == chess.QUEEN:
                        legal_moves_map[key] = m
                
                sq1, sq2 = changed_squares[0], changed_squares[1]
                fast_move = legal_moves_map.get(f"{sq1}{sq2}") or legal_moves_map.get(f"{sq2}{sq1}")
                if fast_move:
                    best_seq = [fast_move]
            
            if not best_seq:
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

    def get_top_moves(self, limit=3, time_left=60.0):
        """Lấy danh sách Top N nước đi tốt nhất từ Stockfish"""
        if not self.engine:
            return []
            
        import random
        human_error_rate = self.config.get("human_error_rate", 0.0)
        
        # Override nếu thời gian đang rất thấp (Scramble Mode)
        engine_time_limit = self.config["time_limit"]
        is_human_error = False
        
        if time_left <= 5.0:
            engine_time_limit = 0.01
            limit = 1
        elif time_left <= 15.0:
            engine_time_limit = min(0.05, engine_time_limit)
            limit = 1
        else:
            is_human_error = random.random() < human_error_rate
        
        # Lấy dư ra 1 nước nếu có kích hoạt Human Error
        # Nâng MultiPV lên để lấy 4-5 nước đi khi kích hoạt Human Error
        actual_search = max(limit + 4, 5) if is_human_error else limit
        
        try:
            with self.lock:
                board_copy = self.board.copy()
                
            if self.config.get("uci_limit_strength"):
                top_moves = []
                banned_moves = set()
                
                # Vòng lặp liên tục gọi hàm play() để lấy ra N nước đi theo chuẩn Elo
                for _ in range(actual_search):
                    legal_moves = [m for m in board_copy.legal_moves if m not in banned_moves]
                    if not legal_moves:
                        break
                        
                    result = self.engine.play(board_copy, chess.engine.Limit(time=engine_time_limit), root_moves=legal_moves, info=chess.engine.INFO_ALL)
                    if not result.move:
                        break
                        
                    best_move = result.move.uci()
                    is_capture = board_copy.is_capture(result.move)
                    
                    score_str = "Elo " + str(self.config["uci_elo"])
                    sort_val = 0
                    
                    if result.info and "score" in result.info:
                        score_obj = result.info["score"].white()
                        if score_obj.is_mate():
                            mate_in = score_obj.mate()
                            score_str = f"M{mate_in}"
                        else:
                            val = score_obj.score() / 100.0
                            score_str = f"+{val:.2f}" if val > 0 else f"{val:.2f}"
                            
                        pov_score = result.info["score"].pov(board_copy.turn)
                        if pov_score.is_mate():
                            m_val = pov_score.mate()
                            if m_val > 0:
                                sort_val = 100000 - m_val
                            else:
                                sort_val = -100000 - m_val
                        else:
                            sort_val = pov_score.score()
                    
                    # Chế độ BM (Ăn quân tuyệt đối): Nếu lợi thế >= BM Threshold, ưu tiên ăn quân hơn cả Mate
                    # Nếu chưa lợi thế, cộng Trade Bias để khuyến khích trao đổi quân
                    bm_thresh = self.config.get("bm_threshold", 400)
                    trade_b = self.config.get("trade_bias", 150)
                    if is_capture:
                        if sort_val >= bm_thresh:
                            sort_val += 200000
                        elif sort_val > 0:
                            sort_val += trade_b
                            
                    pv_list = []
                    if result.info and "pv" in result.info:
                        pv_list = [m.uci() for m in result.info["pv"]]
                    
                    top_moves.append({
                        "move": best_move, 
                        "score": score_str, 
                        "sort_val": sort_val,
                        "pv": pv_list
                    })
                    banned_moves.add(result.move)
                
            else:
                # Nếu không giới hạn sức mạnh (Max), dùng analyse() để lấy Top nước đi mạnh nhất
                info = self.engine.analyse(
                    board_copy, 
                    chess.engine.Limit(time=engine_time_limit), # Giới hạn thời gian suy nghĩ
                    multipv=actual_search
                )
            
                top_moves = []
                for entry in info:
                    if "pv" in entry:
                        best_move_obj = entry["pv"][0]
                        best_move = best_move_obj.uci() # pv là list các nước đi tiếp theo (Principal Variation)
                        is_capture = board_copy.is_capture(best_move_obj)
                        score_obj = entry["score"].white()
                        
                        # Quy đổi điểm số
                        if score_obj.is_mate():
                            mate_in = score_obj.mate()
                            score = f"M{mate_in}"
                        else:
                            val = score_obj.score() / 100.0
                            score = f"+{val:.2f}" if val > 0 else f"{val:.2f}"
                            
                        pov_score = entry["score"].pov(board_copy.turn)
                        sort_val = 0
                        if pov_score.is_mate():
                            m_val = pov_score.mate()
                            if m_val > 0:
                                sort_val = 100000 - m_val
                            else:
                                sort_val = -100000 - m_val
                        else:
                            sort_val = pov_score.score()
                            
                        top_moves.append({
                            "move": best_move,
                            "score": score,
                            "sort_val": sort_val,
                            "pv": [m.uci() for m in entry["pv"]]
                        })
                    
            top_moves.sort(key=lambda x: x["sort_val"], reverse=True)
            
            # Override: Không giả lập lỗi nếu có cơ hội chiếu hết trong <= 4 nước
            if is_human_error and len(top_moves) > 0:
                if top_moves[0]["score"].startswith("M"):
                    m_val = top_moves[0]["score"][1:].lstrip("-")
                    if m_val.isdigit() and int(m_val) <= 4:
                        is_human_error = False
                    
            # Smart Human Error
            if is_human_error and len(top_moves) > 1:
                best_score_val = top_moves[0]["sort_val"]
                candidates = []
                
                for i in range(1, len(top_moves)):
                    diff = best_score_val - top_moves[i]["sort_val"]
                    # Lọc nước Okay Move: rớt Eval từ 80 đến 250 centipawns
                    if 80 <= diff <= 250:
                        # Anti-blunder: Nếu thế cờ đang >= -1.0, không chọn nước rớt xuống < -2.0
                        if best_score_val >= -100 and top_moves[i]["sort_val"] < -200:
                            continue
                        candidates.append(i)
                        
                if candidates:
                    selected_idx = random.choice(candidates)
                    selected_move = top_moves.pop(selected_idx)
                    top_moves.insert(0, selected_move)
                    top_moves.pop(1)
                    print(f"[Engine] 🎭 Smart Human Error: Đã chọn nước top {selected_idx+1} thay thế!")
                else:
                    if top_moves[1]["sort_val"] > -300:
                        top_moves.pop(0)
                        print("[Engine] 🎭 Kích hoạt Human Error: Đang hiển thị nước Inaccuracy thay thế!")
                    else:
                        print("[Engine] 🎭 Hủy Human Error vì các nước thay thế đều là Blunder chí mạng!")
            # [TỐI ƯU] Predictive Premove Check
            if len(top_moves) > 0 and len(top_moves[0].get("pv", [])) >= 3:
                pv = top_moves[0]["pv"]
                our_move_uci = pv[0]
                opp_move_uci = pv[1]
                our_premove_uci = pv[2]
                
                board_test = board_copy.copy()
                try:
                    board_test.push(chess.Move.from_uci(our_move_uci))
                    # Nếu đối thủ chỉ có 1 nước đi duy nhất, ta chắc chắn họ sẽ đi nước đó
                    if len(list(board_test.legal_moves)) == 1:
                        top_moves[0]["forced_premove"] = {
                            "expected_opp_move": opp_move_uci,
                            "our_premove": our_premove_uci
                        }
                except Exception:
                    pass

            return top_moves[:limit]
            
        except Exception as e:
            print(f"[Engine] Lỗi phân tích: {e}")
            return []

    def close(self):
        """Đóng an toàn Stockfish khi tắt app"""
        if self.engine:
            try:
                self.engine.quit()
            except Exception as e:
                print(f"[Engine] Đã ngắt kết nối Stockfish (Tiến trình có thể đã tự đóng trước đó).")
