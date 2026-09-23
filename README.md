# IT5005 Sudoku Assignment

This repository implements a propositional-logic Sudoku solver for IT5005. It
builds both a general CNF knowledge base and a definite-clause knowledge base,
then solves puzzles with forward or backward chaining.

## Files

- `sudoku_solver.py` contains the knowledge-base builders and inference-based
  full-grid solvers.
- `Sudoku_Assignment.ipynb` contains the assignment answers and verification.
- `sudoku_app.py` provides the Streamlit interface and tutor-style reasoning
  trace.
- `puzzles.json` contains the supplied puzzles and expected solutions.
- `logic_.py` and `utils.py` are the supplied support modules.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run sudoku_app.py
```

## Live application

[Open the deployed Sudoku solver](https://it5005-sudoku-assignment-8tp43hu65e437udc9mdzms.streamlit.app/)

The forward solver uses the supplied `logic_.py` implementation of
`pl_fc_entails`; the backward solver is implemented in `sudoku_solver.py` as
required by the assignment.
