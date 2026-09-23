"""IT5005 Assignment 1: student implementation file.

Implement the functions marked below. Do not modify utils.py or logic_.py.
"""

from utils import expr
from logic_ import (
    PropDefiniteKB,
    PropKB,
    associate,
    conjuncts,
    defaultdict,
    parse_definite_clause,
    pl_fc_entails,
)


# Do not change this function; it is used to create atomic propositions.
def atom(prefix, r, c, v):
    """prefix is 'Is' or 'Not'. Returns the Expr for e.g. Is3_2_4."""
    return expr(f'{prefix}{r}_{c}_{v}')


class _IndexedPropDefiniteKB(PropDefiniteKB):
    """PropDefiniteKB with the premise lookup cached for faster queries."""

    def __init__(self):
        super().__init__()
        self._clauses_by_premise = defaultdict(list)
        self._visited_by_forward_chaining = set()

    def tell(self, sentence):
        super().tell(sentence)
        if sentence.op == '==>':
            for premise in conjuncts(sentence.args[0]):
                self._clauses_by_premise[premise].append(sentence)

    def clauses_with_premise(self, premise):
        # pl_fc_entails calls this for every fact it processes. Recording those
        # facts lets a full-grid solve reuse one complete library inference run.
        self._visited_by_forward_chaining.add(premise)
        return self._clauses_by_premise.get(premise, ())


def _peer_cells(n, box_h, box_w, r, c):
    """Return all cells that share a row, column, or box with (r, c)."""
    peers = set()
    for cc in range(1, n + 1):
        if cc != c:
            peers.add((r, cc))
    for rr in range(1, n + 1):
        if rr != r:
            peers.add((rr, c))

    box_r0 = ((r - 1) // box_h) * box_h + 1
    box_c0 = ((c - 1) // box_w) * box_w + 1
    for rr in range(box_r0, box_r0 + box_h):
        for cc in range(box_c0, box_c0 + box_w):
            if (rr, cc) != (r, c):
                peers.add((rr, cc))
    return peers


def build_general_kb(n, box_h, box_w, givens):
    """Return a PropKB encoding this n x n Sudoku's constraints plus givens.

    The encoding uses Is_rcv atoms and CNF clauses for:
    - at least one value per cell,
    - at most one value per cell,
    - row uniqueness,
    - column uniqueness,
    - box uniqueness,
    - the supplied givens.
    """
    kb = PropKB()

    # 1. Every cell has at least one value.
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            kb.tell(associate('|', [atom('Is', r, c, v) for v in range(1, n + 1)]))

            # 2. Every cell has at most one value.
            for v1 in range(1, n + 1):
                for v2 in range(v1 + 1, n + 1):
                    kb.tell(~atom('Is', r, c, v1) | ~atom('Is', r, c, v2))

    # 3. Row uniqueness and 4. column uniqueness.
    for r in range(1, n + 1):
        for c1 in range(1, n + 1):
            for c2 in range(c1 + 1, n + 1):
                for v in range(1, n + 1):
                    kb.tell(~atom('Is', r, c1, v) | ~atom('Is', r, c2, v))

    for c in range(1, n + 1):
        for r1 in range(1, n + 1):
            for r2 in range(r1 + 1, n + 1):
                for v in range(1, n + 1):
                    kb.tell(~atom('Is', r1, c, v) | ~atom('Is', r2, c, v))

    # 5. Box uniqueness.
    for br in range(1, n + 1, box_h):
        for bc in range(1, n + 1, box_w):
            cells = [
                (r, c)
                for r in range(br, br + box_h)
                for c in range(bc, bc + box_w)
            ]
            for i, (r1, c1) in enumerate(cells):
                for r2, c2 in cells[i + 1:]:
                    for v in range(1, n + 1):
                        kb.tell(~atom('Is', r1, c1, v) | ~atom('Is', r2, c2, v))

    # 6. Givens.
    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    return kb


def build_definite_kb(n, box_h, box_w, givens):
    """Return a PropDefiniteKB using elimination + last-candidate reasoning.

    The definite/Horn representation cannot directly state the disjunctive
    "at least one value" constraint. Instead, it uses positive Is/Not atoms:
    an Is fact eliminates the same value from peer cells (and other values
    from the same cell), while a cell whose other candidates have all been
    eliminated gets a last-candidate rule concluding its remaining Is atom.
    """
    kb = _IndexedPropDefiniteKB()

    # Fixed givens are base facts.
    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    for r in range(1, n + 1):
        for c in range(1, n + 1):
            peers = _peer_cells(n, box_h, box_w, r, c)

            for v in range(1, n + 1):
                is_rcv = atom('Is', r, c, v)

                # If this cell has value v, it cannot have any other value.
                for other_v in range(1, n + 1):
                    if other_v != v:
                        kb.tell(is_rcv |'==>'| atom('Not', r, c, other_v))

                # If this cell has value v, every peer is forbidden from v.
                for pr, pc in peers:
                    kb.tell(is_rcv |'==>'| atom('Not', pr, pc, v))

                # Last-candidate rule: if every other value has been eliminated
                # from this cell, then v is the only remaining candidate.
                cell_premises = [
                    atom('Not', r, c, other_v)
                    for other_v in range(1, n + 1)
                    if other_v != v
                ]
                kb.tell(associate('&', cell_premises) |'==>'| is_rcv)

                # Hidden-single rules: if every other cell in a unit is unable
                # to take v, then this cell must take v. These rules supply the
                # "at least one value in each unit" consequence in Horn form.
                row_premises = [
                    atom('Not', r, cc, v)
                    for cc in range(1, n + 1) if cc != c
                ]
                kb.tell(associate('&', row_premises) |'==>'| is_rcv)

                col_premises = [
                    atom('Not', rr, c, v)
                    for rr in range(1, n + 1) if rr != r
                ]
                kb.tell(associate('&', col_premises) |'==>'| is_rcv)

                box_premises = [
                    atom('Not', rr, cc, v)
                    for rr, cc in peers
                    if ((rr - 1) // box_h == (r - 1) // box_h and
                        (cc - 1) // box_w == (c - 1) // box_w)
                ]
                kb.tell(associate('&', box_premises) |'==>'| is_rcv)

    return kb


def _prepare_definite_index(kb):
    """Build reusable fact/rule indexes on a PropDefiniteKB."""
    if hasattr(kb, '_facts') and hasattr(kb, '_rules_by_conclusion'):
        return

    facts = set()
    rules = defaultdict(list)
    for clause in kb.clauses:
        if clause.op == '==>':
            premises, conclusion = parse_definite_clause(clause)
            rules[conclusion].append(tuple(premises))
        else:
            facts.add(clause)
    kb._facts = facts
    kb._rules_by_conclusion = dict(rules)


def solve_full_grid_fc(n, box_h, box_w, givens):
    """Solve the whole puzzle using the supplied forward-chaining function."""
    kb = build_definite_kb(n, box_h, box_w, givens)

    # This atom is outside every valid Sudoku query. Asking the supplied
    # pl_fc_entails function about it makes that function exhaust its agenda;
    # the indexed KB records every fact the library routine processes. This
    # avoids reimplementing forward chaining and avoids repeating the same
    # complete inference run hundreds of times for one grid.
    sentinel = atom('Is', 0, 0, 0)
    kb._visited_by_forward_chaining.clear()
    pl_fc_entails(kb, sentinel)
    inferred = kb._visited_by_forward_chaining

    solved = {}
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            values = [
                v for v in range(1, n + 1)
                if atom('Is', r, c, v) in inferred
            ]
            if len(values) != 1:
                raise ValueError(f'Expected exactly one entailed value for cell ({r}, {c}), got {values}')
            solved[(r, c)] = values[0]
    return solved


def _backward_goal_closure(kb, query):
    """Goal-directed Horn reasoning: collect only rules reachable from query."""
    _prepare_definite_index(kb)

    relevant_goals = {query}
    pending = [query]
    relevant_rules = []
    seen_rules = set()

    # Use an explicit stack rather than Python recursion. Sudoku's cyclic Horn
    # dependency graph can exceed Python's recursion limit, but this performs
    # the same goal-directed expansion safely.
    while pending:
        goal = pending.pop()
        for premises in kb._rules_by_conclusion.get(goal, ()):
            rule_key = (goal, premises)
            if rule_key in seen_rules:
                continue
            seen_rules.add(rule_key)
            relevant_rules.append((premises, goal))
            for premise in premises:
                if premise not in relevant_goals:
                    relevant_goals.add(premise)
                    pending.append(premise)

    inferred = set(kb._facts) & relevant_goals
    rules_with_premise = defaultdict(list)
    counts = []
    for idx, (premises, conclusion) in enumerate(relevant_rules):
        counts.append(len(premises))
        for premise in premises:
            rules_with_premise[premise].append(idx)

    agenda = list(inferred)
    while agenda:
        fact = agenda.pop()
        if fact == query:
            return True
        for idx in rules_with_premise.get(fact, ()):
            counts[idx] -= 1
            if counts[idx] == 0:
                conclusion = relevant_rules[idx][1]
                if conclusion not in inferred:
                    inferred.add(conclusion)
                    agenda.append(conclusion)

    return query in inferred


def pl_bc_entails(kb, query):
    """Return True iff query is entailed by a propositional definite KB.

    This is a goal-directed backward-chaining procedure. It starts from the
    query, recursively expands only rules whose conclusion can prove that goal,
    memoizes the relevant dependency graph, and then evaluates that finite
    dependency graph to a fixed point. The finite propositional vocabulary and
    visited-goal/rule sets guarantee termination even when rules contain cycles.
    """
    return _backward_goal_closure(kb, query)


def solve_full_grid_bc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + pl_bc_entails."""
    kb = build_definite_kb(n, box_h, box_w, givens)
    solved = {}
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            value = None
            for v in range(1, n + 1):
                if pl_bc_entails(kb, atom('Is', r, c, v)):
                    value = v
                    break
            if value is None:
                raise ValueError(f'No entailed value for cell ({r}, {c})')
            solved[(r, c)] = value
    return solved
