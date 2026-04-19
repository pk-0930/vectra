# Frame Annotation

## Overview

We are already showing the frame to the user based on the view classification like mentioned below,
- For side view videos, we try to show the captured bottom frame on a per-rep basis.
- For front view videos, we try to show one single frame.

The frames should be annotated which can give Vectra,
- Visual proof
- Easier coach trust


## What to Annotate

### For side view frame on the selected bottom frame, draw:
- hip line
- knee line
- torso line
- lables:
    - depth status
    - torso lean status

### For front view frame on the selected frame, draw:
- left/right knee points
- left/right ankle points
- knee width line
- ankle width line
- lablel
    - knee tracking status


## Technical Consideration

Every changes must be made in backend part and no UI changes should be involved. The Annotation remains to be a core business logic and must be re-used for other analysis like deadlift or bench press as they are introduced to the system.


## Cautions

The existing functionality should not be touched and should work like before.

## Defect-1

The frames are annotated and works as expected. But there is an inconsistency in annotated line. For example the below mentiones 3 frames has annotations but it is not consistent,

outputs/frames/front_view_squat_knee_frame_190 - has thin annotated line
outputs/frames/squats_side_view_rep_1_frame_24, - has thin annotated line
outputs/frames/side_view_squat_rep_6_frame_314 - has thick annotated line

The expectation is to have thick annotated lines. Thick lines would be easier to see for the naked eyes.
