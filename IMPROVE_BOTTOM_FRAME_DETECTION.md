# Improve Side-View Bottom Frame Detection

## Overview

When testing a side view video, the results in UI seems good. Rep count, Depth Detection and Torso lean results seems mostly accurate. But the Bottom Frame number along with the displayed frame seems to be not the actual bottom frame. When comparing the result vs the actual is slightly different.


## Returned Result (vs) Actual Bottom Frame

- rep 1 - 24 (bottom frame from UI), 24 (actual bottom frame)
- rep 2 - 70 (bottom frame from UI), 72 (actual bottom frame)
- rep 3 - 122 (bottom frame from UI), 120 (actual bottom frame)
- rep 4 - 167 (bottom frame from UI), 169 (actual bottom frame)
- rep 5 - 221 (bottom frame from UI), 220 (actual bottom frame)
- rep 6 - 267 (bottom frame from UI), 270 (actual bottom frame)
- rep 7 - 317 (bottom frame from UI), 319 (actual bottom frame)
- rep 8 - 367 (bottom frame from UI), 369 (actual bottom frame)

The original extracted frames path - `/Users/padmakumar0930/Vectra/MobilityDetectionSystem/mobility-ai-service/frames/squats_side_view`


## Caution

The existing functionality of the side and front view should not be affected.
