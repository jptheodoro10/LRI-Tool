from app.domain.phases import advance_phase
from app.models.enums import RunStatus
from app.repositories import InviteRepository, ParticipantRepository, RunRepository


class PhaseAdvanceBlockedError(ValueError):
    pass


class RunService:
    def __init__(
        self,
        run_repo: RunRepository,
        participant_repo: ParticipantRepository,
        invite_repo: InviteRepository,
    ):
        self.run_repo = run_repo
        self.participant_repo = participant_repo
        self.invite_repo = invite_repo

    def create_run(self, owner_user_id: int, title: str, ai_mode_enabled: bool = True):
        run = self.run_repo.create(owner_user_id=owner_user_id, title=title, ai_mode_enabled=ai_mode_enabled)
        if not self.participant_repo.find_by_user(run.id, owner_user_id):
            self.participant_repo.create_with_user(run.id, owner_user_id, role='facilitator')
        return run

    def list_runs(self, owner_user_id: int):
        return self.run_repo.list_by_owner(owner_user_id)

    def get_owned_run(self, run_id: int, owner_user_id: int):
        run = self.run_repo.get(run_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise ValueError('Run not found')
        return run

    def get_run_for_participant(self, run_id: int, participant_id: int):
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')
        participant = self.participant_repo.get(participant_id)
        if participant is None or participant.run_id != run_id:
            raise ValueError('Run not found')
        return run

    def advance_phase(self, run_id: int, owner_user_id: int):
        run = self.get_owned_run(run_id, owner_user_id)
        if run.current_phase == 2 and run.current_cycle == 1 and self.invite_repo.count_by_run(run.id) < 1:
            raise PhaseAdvanceBlockedError('Generate at least one invite link in phase 2 before advancing to phase 3.')
        next_phase = advance_phase(run.current_phase)

        # Phase 3 must always start from blank canvases.
        # Keep previous phase-2 content in history only; clear current-cycle responses
        # before entering phase 3 so both facilitator and participants see empty boards.
        if run.current_phase == 2 and next_phase == 3:
            self.run_repo.clear_canvas_responses_for_cycle(run.id, run.current_cycle)

        self.run_repo.set_phase(run, next_phase)
        return run

    def update_run(self, run_id: int, owner_user_id: int, *, ai_mode_enabled: bool | None = None, title: str | None = None):
        run = self.get_owned_run(run_id, owner_user_id)
        self.run_repo.update(run, ai_mode_enabled=ai_mode_enabled, title=title)
        return run

    def finalize_run(self, run_id: int, owner_user_id: int):
        run = self.get_owned_run(run_id=run_id, owner_user_id=owner_user_id)
        if run.current_phase != 5:
            raise ValueError('Decision can only be recorded in phase 5')
        run.current_phase = max(5, run.current_phase)
        self.run_repo.set_status(run, RunStatus.COMPLETED)
        return run

    def pivot_run(self, run_id: int, owner_user_id: int):
        run = self.get_owned_run(run_id=run_id, owner_user_id=owner_user_id)
        if run.current_phase != 5:
            raise ValueError('Decision can only be recorded in phase 5')

        self.run_repo.set_phase(run, 2)
        self.run_repo.set_cycle(run, run.current_cycle + 1)
        self.run_repo.set_status(run, RunStatus.ACTIVE)
        return run

    def list_participants(self, run_id: int, owner_user_id: int):
        self.get_owned_run(run_id, owner_user_id)
        return self.participant_repo.list_by_run(run_id)

    def delete_run(self, run_id: int, owner_user_id: int):
        run = self.get_owned_run(run_id, owner_user_id)
        self.run_repo.delete_cascade(run.id)
