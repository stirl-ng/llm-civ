# TODO

The work order is in [`target-architecture.md`](target-architecture.md#build-order). Items here are smaller items that fit into that order.

## Game Bridge (DLL)

- Protocol v2: TCP transport, version + handshake, remove `session_id` from all payloads (`CvGame.cpp`, `GetSessionId()` in `GameStatePipe.cpp`).
- Settler and worker actions that are still missing (see `docs/information-gaps.md`).
- Expose settle-site data (`CvPlayer::GetBestSettlePlot` / `PlotFoundValue`) as information for the LLM. It must not choose the site.

## Game Server views

- City growth (turns to next population) and yields in the city view.
- All other gaps: `docs/information-gaps.md`.
