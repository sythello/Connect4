# Connect4

Connect4 game engine with two interactive frontends:

- A local desktop UI built with Tkinter
- A notebook UI built with `ipywidgets` and `matplotlib`

The repository also includes a simple AI interface, a sample `RandomAI`, and a stronger depth-limited `MinimaxAI`.

## Installation

From the project root:

```bash
python -m pip install -e .
```

This installs the package in editable mode so the script and import examples below can resolve `connect4` from `src/`.

## Current Supported Usages

These are the usage paths currently supported by the code in this repository.

### 1. Run the desktop Tkinter app

```bash
python scripts/run_game_tkint.py
```

This launches the local desktop game window using [`Connect4TkApp`](src/connect4/ui/tkinter_ui.py).

The desktop app now uses a two-step flow:

- `Game Setup` mode for choosing Player 1 and Player 2 as either `Human` or a configured AI version
- `Playing` mode for the board, move log, result banner, plus top-right `Restart` and `Back` actions

The supported desktop AI options are loaded from [`src/connect4/ui/ai_options.json`](src/connect4/ui/ai_options.json).

### 2. Run the notebook widget app

Use this inside Jupyter Notebook, JupyterLab, or a similar IPython environment:

```python
from connect4.ui.ipywidgets_ui import Connect4WidgetApp

app = Connect4WidgetApp()
app.display()
```

This renders an interactive board with `ipywidgets` controls and a `matplotlib` board view.

### 3. Use the headless game engine directly

```python
from connect4.core import Connect4Game

game = Connect4Game()
result = game.drop_piece(3)

print(game.board)
print(result)
print(game.valid_moves())
```

The headless engine lives in [`game_core.py`](src/connect4/core/game_core.py) and can be used independently from either UI.

### 4. Implement a custom AI player

Subclass [`Connect4AIPlayer`](src/connect4/ai/ai_base.py) and implement `choose_move(...)`:

```python
from connect4.ai import Connect4AIPlayer

class MyAI(Connect4AIPlayer):
    name = "MyAI"

    def choose_move(self, board, player_id, valid_moves, last_move):
        return valid_moves[0]
```

The repository currently includes two built-in implementations:

- [`RandomAI`](src/connect4/ai/random_ai.py)
- [`MinimaxAI`](src/connect4/ai/minimax_ai.py)

### 5. Evaluate AI strength with the anchored ELO ladder

List the currently registered entrants:

```bash
python scripts/evaluate_ai_strength.py list
```

Calibrate a new entrant into the canonical ladder:

```bash
python scripts/evaluate_ai_strength.py calibration random-v1 --games-per-pair 2 --seed 5
```

This writes ratings to `artifacts/elo_ratings.json` by default. New entrants are rated by playing against:

- the fixed anchor set,
- any already-rated active entrants in the saved ladder.

Run a tournament among already-rated entrants without saving:

```bash
python scripts/evaluate_ai_strength.py full random-v1 minimax-d2-v1 --no-save
```

## Notes

- There is currently no packaged console entry point in `pyproject.toml`.
- The top-level package file [`src/connect4/__init__.py`](src/connect4/__init__.py) is empty, so imports should come from subpackages like `connect4.core`, `connect4.ai`, or `connect4.ui...`.
- The desktop Tkinter UI loads its player list from [`src/connect4/ui/ai_options.json`](src/connect4/ui/ai_options.json), which currently ships with `human`, `random-v1`, `minimax-d2-v1`, and `minimax-d4-v1`.
- The notebook `ipywidgets` UI still uses its built-in `Human`, `AI: RandomAI`, and `AI: MinimaxAI` dropdown options.
- The evaluation ladder treats each AI version as a separate entrant ID. If you change an AI materially, register a new entrant ID instead of reusing an old one.

## Current File Structure

```text
Connect4/
├── README.md
├── pyproject.toml
├── scripts/
│   └── run_game_tkint.py
└── src/
    └── connect4/
        ├── __init__.py
        ├── ai/
        │   ├── __init__.py
        │   ├── ai_base.py
        │   ├── minimax_ai.py
        │   └── random_ai.py
        ├── core/
        │   ├── __init__.py
        │   └── game_core.py
        └── ui/
            ├── __init__.py
            ├── ipywidgets_ui.py
            └── tkinter_ui.py
```

## Main Files

- [`pyproject.toml`](pyproject.toml): package metadata and Python dependencies
- [`scripts/run_game_tkint.py`](scripts/run_game_tkint.py): desktop app launcher
- [`src/connect4/core/game_core.py`](src/connect4/core/game_core.py): headless game engine and move rules
- [`src/connect4/ai/ai_base.py`](src/connect4/ai/ai_base.py): AI base class contract
- [`src/connect4/ai/minimax_ai.py`](src/connect4/ai/minimax_ai.py): depth-limited minimax AI with alpha-beta pruning
- [`src/connect4/ai/random_ai.py`](src/connect4/ai/random_ai.py): sample random-move AI
- [`src/connect4/ui/tkinter_ui.py`](src/connect4/ui/tkinter_ui.py): desktop Tkinter frontend
- [`src/connect4/ui/ipywidgets_ui.py`](src/connect4/ui/ipywidgets_ui.py): notebook frontend
- [`src/connect4/ui/ai_options.json`](src/connect4/ui/ai_options.json): JSON config for Tkinter player options
