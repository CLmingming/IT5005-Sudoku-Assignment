import html
import json
import time
from collections import defaultdict

import streamlit as st

from utils import *
from logic_ import *
from sudoku_solver import (
    atom,
    build_definite_kb,
    build_general_kb,
    solve_full_grid_fc,
    solve_full_grid_bc,
    pl_bc_entails,
)


st.set_page_config(page_title='Sudoku Solver', layout='wide')
st.title('Sudoku Solver')
st.caption('Knowledge representation + forward/backward chaining in propositional logic')

with open('puzzles.json', encoding='utf-8') as f:
    pool = json.load(f)

n = pool['n']
box_h = pool['box_h']
box_w = pool['box_w']
puzzles = pool['puzzles']


def parse_givens(raw_givens):
    return {tuple(int(x) for x in key.split('_')): value
            for key, value in raw_givens.items()}


def render_grid(grid, givens=None, title=None):
    givens = givens or {}
    if title:
        st.subheader(title)
    rows = []
    for r in range(1, n + 1):
        cells = []
        for c in range(1, n + 1):
            value = grid.get((r, c), '')
            text = html.escape(str(value)) if value != '' else '&nbsp;'
            classes = []
            if (r, c) in givens:
                classes.append('given')
            if c % box_w == 0 and c != n:
                classes.append('right-box')
            if r % box_h == 0 and r != n:
                classes.append('bottom-box')
            cells.append(f'<td class="{" ".join(classes)}">{text}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')

    table = '''
    <style>
    .sudoku-wrap {display:flex; justify-content:center; margin:0.5rem 0 1rem 0;}
    table.sudoku {border-collapse:collapse; font-size:1.25rem; box-shadow:0 1px 4px rgba(0,0,0,.12);}
    table.sudoku td {width:42px; height:42px; text-align:center; border:1px solid #bbb;}
    table.sudoku td.given {font-weight:800; background:#eef2ff;}
    table.sudoku td.right-box {border-right:3px solid #555;}
    table.sudoku td.bottom-box {border-bottom:3px solid #555;}
    </style>
    <div class="sudoku-wrap"><table class="sudoku">''' + ''.join(rows) + '</table></div>'
    st.markdown(table, unsafe_allow_html=True)


def symbol_text(symbol):
    text = str(symbol)
    if text.startswith('Is'):
        parts = text[2:].split('_')
        if len(parts) == 3:
            r, c, v = parts
            return f'Cell ({r}, {c}) is {v}'
    if text.startswith('Not'):
        parts = text[3:].split('_')
        if len(parts) == 3:
            r, c, v = parts
            return f'Cell ({r}, {c}) cannot be {v}'
    return text


def rule_text(premises, conclusion):
    if premises:
        premise_text = ', '.join(symbol_text(p) for p in premises)
        return f'Because {premise_text}, deduce {symbol_text(conclusion)}.'
    return f'The fact {symbol_text(conclusion)} is given.'


def build_reasoning_trace(kb, query, max_steps=24):
    """Create a human-readable trace from the goal-relevant Horn dependency graph."""
    # pl_bc_entails builds the reusable rule index on the KB.
    result = pl_bc_entails(kb, query)
    facts = getattr(kb, '_facts', set())
    rules_by_conclusion = getattr(kb, '_rules_by_conclusion', {})

    relevant = {query}
    pending = [query]
    candidate_rules = []
    seen_rules = set()
    while pending:
        goal = pending.pop()
        for premises in rules_by_conclusion.get(goal, ()):
            key = (goal, premises)
            if key in seen_rules:
                continue
            seen_rules.add(key)
            candidate_rules.append((premises, goal))
            for premise in premises:
                if premise not in relevant:
                    relevant.add(premise)
                    pending.append(premise)

    # Evaluate only the relevant rules and retain the first supporting rule.
    inferred = set(facts) & relevant
    support = {}
    remaining = list(candidate_rules)
    changed = True
    while changed:
        changed = False
        for premises, conclusion in remaining:
            if conclusion in inferred:
                continue
            if all(p in inferred for p in premises):
                inferred.add(conclusion)
                support[conclusion] = premises
                changed = True

    if query not in inferred:
        return result, [
            f'Backward search started from {symbol_text(query)}.',
            f'It explored {len(candidate_rules)} goal-relevant rule(s).',
            f'No rule chain established {symbol_text(query)} from the given facts.'
        ]

    steps = [f'Backward search starts with the goal: {symbol_text(query)}.']

    def add_derivation(goal, seen):
        if len(steps) >= max_steps or goal in seen:
            return
        seen.add(goal)
        if goal in facts:
            steps.append(f'Base fact reached: {symbol_text(goal)}.')
            return
        premises = support.get(goal)
        if premises is None:
            steps.append(f'{symbol_text(goal)} is supported by the relevant Horn closure.')
            return
        for premise in premises:
            if len(steps) >= max_steps:
                return
            add_derivation(premise, seen)
        if len(steps) < max_steps:
            steps.append(rule_text(premises, goal))

    add_derivation(query, set())
    steps.append(f'Final result: {symbol_text(query)} is entailed (True).')
    return result, steps


# --- 1. Puzzle selection & visual board display ---
selected_index = st.selectbox(
    'Choose a puzzle',
    options=list(range(len(puzzles))),
    format_func=lambda i: f'Puzzle {i + 1} ({puzzles[i]["given_count"]} givens)',
)
selected = puzzles[selected_index]
givens = parse_givens(selected['givens'])

empty_grid = {(r, c): givens.get((r, c), '')
              for r in range(1, n + 1) for c in range(1, n + 1)}
render_grid(empty_grid, givens, 'Initial puzzle')

st.info('Bold/blue cells are the original givens. Blank cells are the values the solver must infer.')

# --- 2. Full-grid auto-solver, with algorithm selection ---
st.subheader('Full-grid solver')
algorithm = st.radio(
    'Inference algorithm',
    ['Forward chaining', 'Backward chaining'],
    horizontal=True,
)

if st.button('Solve full grid', type='primary'):
    solver = solve_full_grid_fc if algorithm == 'Forward chaining' else solve_full_grid_bc
    start = time.perf_counter()
    solved = solver(n, box_h, box_w, givens)
    elapsed = time.perf_counter() - start
    st.session_state[f'solved_{selected_index}'] = solved
    st.session_state[f'time_{selected_index}_{algorithm}'] = elapsed

solved = st.session_state.get(f'solved_{selected_index}')
if solved:
    render_grid(solved, givens, 'Solved grid')
    elapsed = st.session_state.get(f'time_{selected_index}_{algorithm}')
    if elapsed is not None:
        st.metric('Last solve time', f'{elapsed:.4f} seconds')

# --- 3. Targeted cell entailment query ---
st.subheader('Targeted entailment query')
qcol1, qcol2, qcol3 = st.columns(3)
with qcol1:
    qr = st.number_input('Row (r)', min_value=1, max_value=n, value=1, step=1)
with qcol2:
    qc = st.number_input('Column (c)', min_value=1, max_value=n, value=1, step=1)
with qcol3:
    qv = st.number_input('Value (v)', min_value=1, max_value=n, value=1, step=1)

if st.button('Check entailment'):
    definite_kb = build_definite_kb(n, box_h, box_w, givens)
    query = atom('Is', int(qr), int(qc), int(qv))
    answer, trace = build_reasoning_trace(definite_kb, query)
    st.session_state[f'query_result_{selected_index}'] = answer
    st.session_state[f'query_trace_{selected_index}'] = trace

query_key = f'query_result_{selected_index}'
if query_key in st.session_state:
    answer = st.session_state[query_key]
    st.write(f'Is({int(qr)}, {int(qc)}, {int(qv)})')
    if answer:
        st.success('True: the KB entails this value.')
    else:
        st.error('False: the KB does not entail this value.')

# --- 4. Reasoning trace / tutor mode ---
st.subheader('Tutor mode: reasoning trace')
trace_key = f'query_trace_{selected_index}'
if trace_key in st.session_state:
    for i, sentence in enumerate(st.session_state[trace_key], start=1):
        with st.expander(f'Step {i}', expanded=(i <= 3)):
            st.write(sentence)
else:
    st.write('Run a targeted entailment query to see the goal-directed reasoning trace.')

st.caption('Core inference functions live in sudoku_solver.py; this app only provides the interface and explanation layer.')
