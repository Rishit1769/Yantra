from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from yantra.core.errors import InvalidStateTransitionError
from yantra.core.states import RunState, RunStateRecord, is_terminal_state, transition_state


def state_record(state: RunState = RunState.CREATED) -> RunStateRecord:
    return RunStateRecord(run_id=uuid4(), session_id=uuid4(), agent_id="test.agent", state=state)


def test_valid_state_path_and_terminal_states() -> None:
    record = state_record()
    for target in (
        RunState.QUEUED,
        RunState.RUNNING,
        RunState.WAITING_FOR_MODEL,
        RunState.RUNNING,
        RunState.COMPLETED,
    ):
        record = transition_state(record, target)

    assert record.state == RunState.COMPLETED
    assert record.version == 5
    assert is_terminal_state(record.state)


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (RunState.CREATED, RunState.RUNNING),
        (RunState.WAITING_FOR_MODEL, RunState.WAITING_FOR_TOOL),
        (RunState.COMPLETED, RunState.RUNNING),
        (RunState.FAILED, RunState.QUEUED),
        (RunState.CANCELLED, RunState.COMPLETED),
    ],
)
def test_invalid_transitions_are_rejected(start: RunState, target: RunState) -> None:
    with pytest.raises(InvalidStateTransitionError):
        transition_state(state_record(start), target)


@settings(derandomize=True, max_examples=50)
@given(st.sampled_from([RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED]))
def test_all_terminal_states_reject_every_transition(terminal: RunState) -> None:
    record = state_record(terminal)
    for target in RunState:
        with pytest.raises(InvalidStateTransitionError):
            transition_state(record, target)
