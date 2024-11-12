import time

from stockfish import Stockfish
import matplotlib.pyplot as plt
from tkinter import messagebox
from PIL import Image, ImageTk
from chess import Board
import subprocess
import threading
import tkinter
import math
import sys
import re

window_width = 904
window_height = 904

# Width / Height
board_grid = [8, 8]

stockfish = Stockfish(
    path="stockfish.exe",
    depth=20,
    parameters={
        "Threads": 5,
        "Minimum Thinking Time": 1,
    }
)

evaluation = []
differences = []

Openings = []
photos = []
moves = []


MAX_DISTANCE = 400
WHITE = 'w'
BLACK = 'b'

highlight_color = "#F8EC5A"
primary_color = "#769656"
secondary_color = "#EEEED2"

# Move a piece
selected_algebraic_notation = ""

# Evaluate the move
previous_value = 0
# Should eval? Eval Type, x, y
evaluate = [False, "None", 0.0, 0.0, '#c0c08c']

# Create window and canvas
window = tkinter.Tk()
window.title("Stockfish")
window.resizable(False, False)

screen_width = window.winfo_screenwidth()
screen_height = window.winfo_screenheight()

position_x = (screen_width - window_width) // 2
position_y = (screen_height - window_height) // 2

window.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

canvas = tkinter.Canvas(window, width=window_width, height=window_height, highlightthickness=0)
canvas.pack()

current_move_index = -1

def submit_pgn():
    """Process PGN input from the popup."""
    pgn_text = pgn_entry.get("1.0", tkinter.END).strip()
    if pgn_text:
        parse_pgn(pgn_text)
        messagebox.showinfo("Success", "PGN loaded successfully!")
    else:
        messagebox.showwarning("Warning", "Please enter a PGN before submitting.")


def open_pgn_popup():
    # Create a new top-level window
    popup = tkinter.Toplevel(window)
    popup.title("Enter PGN")
    popup.geometry("400x300")

    # Label
    label = tkinter.Label(popup, text="Paste your PGN here:")
    label.pack(pady=5)

    # Text field for PGN input
    global pgn_entry
    pgn_entry = tkinter.Text(popup, wrap="word", height=10)
    pgn_entry.pack(expand=True, fill="both", padx=10, pady=10)

    # Submit button
    submit_button = tkinter.Button(popup, text="Submit", command=submit_pgn)
    submit_button.pack(pady=5)


def parse_pgn(pgn_text):
    global moves

    header_pattern = r"\[.*?\]"
    headers = re.findall(header_pattern, pgn_text)
    moves_text = re.sub(header_pattern, "", pgn_text).strip()
    
    moves = re.split(r"\d+\.\s*", moves_text)
    moves = [move.strip() for move in moves if move] 

    cleaned_moves = []
    for move in moves:
        half_moves = move.split()
        cleaned_moves.extend(half_moves)

    moves = san_to_lan_moves(cleaned_moves)

    return headers, cleaned_moves

def san_to_lan_moves(pgn_moves):
    global moves

    board = Board()
    lan_moves = []

    for san_move in pgn_moves:
        try:
            move = board.parse_san(san_move)
            lan_moves.append(move.uci())
            board.push(move)
        except ValueError as e:
            print(f"Error parsing move '{san_move}': {e}")
            break
    
    return lan_moves


def navigate_moves(event):
    global current_move_index
    if event.keysym == "Right":
        current_move_index += 1
    elif event.keysym == "Left":
        current_move_index -= 1

    display_current_move()

# Key bindings for move navigation
window.bind("<Left>", navigate_moves)
window.bind("<Right>", navigate_moves)


previous_value = 0
def display_current_move():
    global evaluate, difference, previous_value

    # Initialize previous_value if this is the first move
    if 'previous_value' not in globals():
        previous_value = 0.0
    
    # Set the current position in Stockfish for evaluation
    if 0 <= current_move_index < len(moves):
        is_best_move = False
        if stockfish.get_best_move() == moves[current_move_index]:
            is_best_move = True

        stockfish.set_position(moves[:current_move_index + 1])

        current_evaluation = stockfish.get_evaluation()['value']

        # if current_evaluation['type'] == 'cp':
        #     current_value = current_evaluation['value'] / 100.0
        # elif current_evaluation['type'] == 'mate':
        #     current_value = 100 if current_evaluation['value'] > 0 else -100
        # else:
        #     current_value = 0

        difference = abs(round(previous_value - current_evaluation / 100, 2))
        previous_value = round(current_evaluation / 100, 2)

        print(difference)
        if is_best_move:
            evaluate[1] = "best"
            evaluate[4] = "#b7c078"
        elif 0 < difference < 0.6:
            evaluate[1] = "excellent"
            evaluate[4] = "#c1c18d"
        elif 0.6 <= difference < 0.9:
            evaluate[1] = "good"
            evaluate[4] = "#c1c18d"
        elif 0.9 <= difference < 1.2:
            evaluate[1] = "inaccuracy"
            evaluate[4] = "#f2c86a"
        elif 1.2 <= difference < 2:
            evaluate[1] = "mistake"
            evaluate[4] = "#eca462"
        else:
            evaluate[1] = "blunder"
            evaluate[4] = "#f38568"

    square_height = window_height / board_grid[1]
    try:
        square_x = ord(moves[current_move_index][-2:][0]) - ord('a')
        square_y = int(moves[current_move_index][-2:][1])
    except:
        square_x = 50
        square_y = 50

    evaluate[0] = True
    evaluate[2] = square_x * square_height
    evaluate[3] = (board_grid[1] - square_y) * square_height

    # Draw the updated position
    draw_fen(stockfish.get_fen_position(), True)


def check_future_evaluation(moves):
    """
    Evaluate the position a few moves ahead to check if the sacrifice pays off.
    """
    stockfish.set_position(moves)
    future_evaluation = stockfish.get_evaluation()['value'] / 100.0  # Convert to centipawns
    return future_evaluation


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def plot_difference_graph():
    # plt.figure(figsize=(10, 6))
    plt.plot(evaluation, marker='o', linestyle='-', color='b')
    plt.title('Difference Variable Over Time')
    plt.xlabel('Move Number')
    plt.ylabel('Difference (Sigmoid Value)')
    plt.grid(True)
    plt.show()


def piece_clicked(event):
    global selected_algebraic_notation, moves, previous_value, evaluate

    canvas.delete("image")
    canvas.delete("selected")

    mouse_x = event.x
    mouse_y = event.y

    square_width = window_width / board_grid[0]
    square_height = window_height / board_grid[1]
    square_x = int(mouse_x // square_width)
    square_y = board_grid[1] - int(mouse_y // square_height)

    letter = str(chr(square_x + ord('A'))).lower()

    if len(selected_algebraic_notation) >= 1 and not(selected_algebraic_notation == letter + str(square_y)):
        if stockfish.is_move_correct(selected_algebraic_notation + letter + str(square_y)):
            moves.append(selected_algebraic_notation + letter + str(square_y))

            is_best_move = False
            if stockfish.get_best_move() == moves[current_move_index]:
                is_best_move = True
            stockfish.set_position(moves)

            evaluation = stockfish.get_evaluation()
            difference = abs(round(previous_value - evaluation['value'] / 100, 2))
            differences.append(difference)

            window.title("Stockfish "+str(round(stockfish.get_evaluation()['value'] / 100, 1)))

            evaluate[0] = True
            evaluate[2] = square_x * square_width
            evaluate[3] = (board_grid[1] - square_y) * square_height

            print(difference)
            if is_best_move:
                evaluate[1] = "best"
            elif 0 < difference < 0.6:
                evaluate[1] = "excellent"
            elif 0.6 <= difference < 0.9:
                evaluate[1] = "good"
            elif 0.9 <= difference < 1.2:
                evaluate[1] = "inaccuracy"
            elif 1.2 <= difference < 2:
                evaluate[1] = "mistake"
            else:
                evaluate[1] = "blunder"

            previous_value = round(evaluation['value'] / 100, 2)
            draw_fen(stockfish.get_fen_position(), True)

        selected_algebraic_notation = ""

    selected_algebraic_notation = letter + str(square_y)

    # Adjusted square_y
    piece = stockfish.get_what_is_on_square(letter + str(square_y))
    piece_moves = []
    if str(piece) == "Piece.WHITE_PAWN" or str(piece) == "Piece.BLACK_PAWN":
        piece_moves = get_pawn_moves(square_x, square_y)

    if str(piece) == "Piece.WHITE_BISHOP" or str(piece) == "Piece.BLACK_BISHOP":
        piece_moves = get_bishop_moves(square_x, square_y)

    if str(piece) == "Piece.WHITE_ROOK" or str(piece) == "Piece.BLACK_ROOK":
        piece_moves = get_rook_moves(square_x, square_y)

    if str(piece) == "Piece.WHITE_QUEEN" or str(piece) == "Piece.BLACK_QUEEN":
        piece_moves = get_bishop_moves(square_x, square_y) + get_rook_moves(square_x, square_y)

    if str(piece) == "Piece.WHITE_KING" or str(piece) == "Piece.BLACK_KING":
        piece_moves = get_king_moves(square_x, square_y)

    if str(piece) == "Piece.WHITE_KNIGHT" or str(piece) == "Piece.BLACK_KNIGHT":
        piece_moves = get_knight_moves(square_x, square_y)

    if len(piece_moves) >= 1:
        for i in range(len(piece_moves)):
            if stockfish.is_move_correct(
                letter + str(square_y) + str(chr(piece_moves[i][0] + ord('A'))).lower() + str(piece_moves[i][1])
            ):
                draw_move_icon(
                    piece_moves[i][0],
                    piece_moves[i][1] + 1,
                    square_width,
                    square_height,
                    str(chr(piece_moves[i][0] + ord('A'))).lower() + str(piece_moves[i][1])
                )


def draw_move_icon(square_x, square_y, square_width, square_height, square):
    image_width = 32
    square_y = board_grid[1] - square_y + 1

    if str(stockfish.get_what_is_on_square(square)) == "None":
        image = Image.open("Images/move.png")
        x = square_x * square_width + square_width / 2 - image_width / 2
        y = square_y * square_height + square_width / 2 - image_width / 2
    else:
        image = Image.open("Images/take.png")
        x = square_x * square_width
        y = square_y * square_height

    photo = ImageTk.PhotoImage(image)
    photos.append(photo)  # Store the photo object in the list

    canvas.create_image(
        x, y,
        image=photo, anchor=tkinter.NW, tags="image"  # Assign a tag to the image
    )


def get_coordinate_from_index(fen, index):
    _x = 0
    _y = 0
    for i in range(len(fen)):
        if fen[i] == "/":
            _x = 0
            _y += 1
        elif fen[i].lower() in ["r", "n", "b", "q", "k", "p"]:
            _x += 1
        elif str(fen[i]) in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            _x += int(fen[i])

        if i == index:
            return _x - 1, board_grid[1] - _y

    return None


def draw_board():
    square_width = window_width / board_grid[0]
    square_height = window_height / board_grid[1]

    for x in range(board_grid[0]):
        index = x
        for y in range(board_grid[1]):
            index += 1

            color = primary_color
            if index % 2:
                color = secondary_color

            canvas.create_rectangle(
                square_width * x,
                square_height * y,
                square_width * x + square_width - 1,
                square_height * y + square_height - 1,
                outline=color,
                fill=color,
            )

def draw_fen(fen, animate):
    global photos
    x = 0
    y = 0

    square_width = window_width / board_grid[0]
    square_height = window_height / board_grid[1]

    canvas.delete("all")
    draw_board()

    photos = []
    for i in range(len(fen)):
        if fen[i] == "/":
            x = 0
            y += 1
        elif fen[i].lower() in ["r", "n", "b", "q", "k", "p"]:
            image_path = "Images/white/" + fen[i] + ".png"
            if fen[i].islower():
                image_path = "Images/black/" + fen[i] + ".png"

            image = Image.open(image_path)
            photo = ImageTk.PhotoImage(image)
            photos.append(photo)  # Store the photo object in the list

            image_x = round(square_width * x)
            image_y = round(square_height * y)

            canvas.create_image(image_x, image_y, anchor=tkinter.NW, image=photo)

            x += 1
        elif str(fen[i]) in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            x += int(fen[i])

    if animate:
        if len(moves) >= 1:
            start_x = square_width * int(ord(moves[current_move_index][0].lower()) - ord('a'))
            start_y = square_height * (board_grid[1] - int(moves[current_move_index][1]))

            target_x = square_width * int(ord(moves[current_move_index][2].lower()) - ord('a'))
            target_y = square_height * (board_grid[1] - int(moves[current_move_index][3]))

            animate_image(start_x, start_y, target_x, target_y)


def animate_image(start_x, start_y, target_x, target_y):
    global evaluate

    square_width = window_width / board_grid[0]
    square_height = window_height / board_grid[1]

    canvas.create_rectangle(
        start_x,
        start_y,
        start_x + square_width - 1,
        start_y + square_height - 1,
        outline=evaluate[4],
        fill=evaluate[4],
        )

    canvas.create_rectangle(
        target_x,
        target_y,
        target_x + square_width - 1,
        target_y + square_height - 1,
        outline=evaluate[4],
        fill=evaluate[4],
        )

    # get the last move e.g moves = ['e2e4'], e4
    # piece = str(stockfish.get_what_is_on_square(moves[-1][2] + moves[-1][3]))
    piece = str(stockfish.get_what_is_on_square(moves[current_move_index][-2:]))
    if piece == "Piece.WHITE_KNIGHT" or piece == "Piece.BLACK_KNIGHT":
        piece = piece[piece.index("_") + 2].lower()
    else:
        piece = piece[piece.index("_") + 1].lower()

    turn = stockfish.get_fen_position()[stockfish.get_fen_position().index(" ") + 1]
    image = tkinter.PhotoImage(file=f"Images/white/{piece}.png" if turn == BLACK else f"Images/black/{piece}.png")

    # Create the image on the canvas at the starting position
    image_item = canvas.create_image(start_x, start_y, image=image, anchor=tkinter.NW)

    dx = target_x - start_x
    dy = target_y - start_y
    distance = round(math.sqrt(dx ** 2 + dy ** 2))

    angle = math.atan2(dy, dx)

    # Adjust the step size for smooth animation
    step_size = distance / map_value(distance, 1, MAX_DISTANCE, 50, 70)

    # Calculate dx and dy components using the angle
    dx = round(step_size * math.cos(angle))
    dy = round(step_size * math.sin(angle))

    animate = True

    def move_image():
        nonlocal start_x, start_y, dx, dy, animate, piece, distance
        global evaluate

        # Update the image position
        start_x += dx
        start_y += dy

        start_x = round(start_x + 0.0)
        start_y = round(start_y + 0.0)

        # Move the image on the canvas
        canvas.coords(image_item, start_x, start_y)

        # Check if the piece has passed the target position
        if (dx > 0 and start_x > target_x) or (dx < 0 and start_x < target_x) or \
                (dy > 0 and start_y > target_y) or (dy < 0 and start_y < target_y):
            # Reverse the direction and move back towards the target
            dx = target_x - start_x
            dy = target_y - start_y

        # Update the remaining distance
        remaining_distance = round(math.sqrt((target_x - start_x) ** 2 + (target_y - start_y) ** 2))
        # Terminate the animation when distance becomes very small
        if remaining_distance <= 0:
            animate = False

            if evaluate[0]:
                image_evaluate = Image.open(f"Images/evaluate/{evaluate[1]}.png")
                photo = ImageTk.PhotoImage(image_evaluate)
                photos.append(photo)

                adjust = 0
                if evaluate[3] == 0:  # Top of screen
                    adjust = 25

                canvas.create_image(
                    evaluate[2] + square_width,
                    evaluate[3] + adjust, anchor=tkinter.CENTER, image=photo
                )

        if animate:
            window.after(1, move_image)

    move_image()
    window.mainloop()


def map_value(value, start1, stop1, start2, stop2):
    # Map value from the range start1-stop1 to the range start2-stop2
    return start2 + (stop2 - start2) * ((value - start1) / (stop1 - start1))


def get_king_moves(current_row, current_col):
    king_moves = []

    # Define the possible offsets for king moves
    offsets = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]

    # Iterate over the offsets
    for offset in offsets:
        row = current_row + offset[0]
        col = current_col + offset[1]

        # Check if the move is within the bounds of the chessboard
        if 0 <= row < board_grid[0] + 1 and 0 <= col < board_grid[1] + 1:
            king_moves.append((row, col))

    return king_moves


def get_rook_moves(current_row, current_col):
    rook_moves = []

    # Iterate over the rows
    for row in range(board_grid[0] + 1):
        # Exclude the current position
        if row != current_row:
            # Add horizontal moves
            rook_moves.append((row, current_col))

    # Iterate over the columns
    for col in range(board_grid[1] + 1):
        # Exclude the current position
        if col != current_col:
            # Add vertical moves
            rook_moves.append((current_row, col))

    return rook_moves


def get_pawn_moves(current_row, current_col):
    pawn_moves = []

    turn = stockfish.get_fen_position()[stockfish.get_fen_position().index(" ") + 1]

    offsets = []
    if turn == WHITE:
        offsets = [(0, 1), (0, 2), (1, 1), (-1, 1)]
    elif turn == BLACK:
        offsets = [(0, -1), (0, -2), (-1, -1), (1, -1)]

    for i in range(len(offsets)):
        row = current_row + offsets[i][0]
        col = current_col + offsets[i][1]

        if 0 <= row < board_grid[0] + 1 and 0 <= col < board_grid[1] + 1:
            pawn_moves.append((row, col))

    return pawn_moves


def get_bishop_moves(current_row, current_col):
    bishop_moves = []
    # Top-left direction
    row = current_row - 1
    col = current_col - 1

    while row >= 0 and col >= 0:
        bishop_moves.append((row, col))
        row -= 1
        col -= 1

    # Top-right direction
    row = current_row - 1
    col = current_col + 1
    while row >= 0 and col < board_grid[0] + 1:
        bishop_moves.append((row, col))
        row -= 1
        col += 1

    # Bottom-left direction
    row = current_row + 1
    col = current_col - 1
    while row < board_grid[1] + 1 and col >= 0:
        bishop_moves.append((row, col))
        row += 1
        col -= 1

    # Bottom-right direction
    row = current_row + 1
    col = current_col + 1
    while row < board_grid[1] + 1 and col < board_grid[0] + 1:
        bishop_moves.append((row, col))
        row += 1
        col += 1

    return bishop_moves


def get_knight_moves(current_row, current_col):
    knight_moves = []

    # Possible knight move offsets
    offsets = [
        (1, 2), (-1, 2), (1, -2), (-1, -2),
        (2, 1), (-2, 1), (2, -1), (-2, -1)
    ]

    for offset in offsets:
        row = current_row + offset[0]
        col = current_col + offset[1]

        if 0 <= row < board_grid[1] + 1 and 0 <= col < board_grid[0] + 1:
            knight_moves.append((row, col))

    return knight_moves


def right_click(event):
    window.title("Stockfish "+str(stockfish.get_evaluation()['value']))


def main():
    # window.protocol("WM_DELETE_WINDOW", lambda: (plot_difference_graph(), window.destroy()))

    # Register the click event handler for the canvas
    canvas.bind("<Button-1>", piece_clicked)
    canvas.bind("<Button-3>", right_click)

    # Set starting fen
    draw_fen(stockfish.get_fen_position(), False)

    open_pgn_popup()

    window.mainloop()


def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])


if __name__ == "__main__":
    file_path = 'C:/Users/Ruben/Desktop/Stockfish/Openings.txt'
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
            for line in lines:
                Openings.append(line.strip())
    except FileNotFoundError:
        print("File not found.")

    main()
    