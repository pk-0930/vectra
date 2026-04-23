# Vectra - Angle based Analysis
## Angle based analysis to build reliable system and fail gracefully.

### Product flaw

Vectra works for side view and front view videos. But even then the views should be uploaded in a way that it has to be perfect side or front view. Even if it is slightly angled, the results might be quite bad. I get it that the depth or torso lean detection even for naked eye needs perfect side view and to detect knee cave for naked eye we need front view to detect correctly. But from product perspective the user has to capture the video in side or front view and they can make mistakes in capturing it in perfect side or front view and when they test their videos they might get quite a bad result and the product might become not trust worthy right or provide results that would feel unreliable. And even from fitness trainers perspective, they might find it difficult to ask to the client to send a perfect side or front view video.

### Flaw improvisation

```text
"Vectra should be excellent at knowing when to analyze the video and when and what rules to apply for that video." 
```

It should not force user to record in any angle. With the available video, Vectra should try to detect and apply rules based on the video and send response. As of now, we are building the Vectra for fitness coaches, so video quality based on the video angle can be marked so that the user would know if it is good or moderate or not sufficient to apply rules. So if it is good then we basically mean that we could apply all the view based rules to that video, for example if it is side view we could apply rep detection, depth detection and torso lean perfectly. If moderate we could detect what rules can realiable results and we apply that rules only and we can provide a response based on that. A "not sufficient" video cannot apply any rules as the video was not of a perfect anlge to apply any rules and we fail gracefully. 

```text
"Vectra should be in a way that the user should not think that the product is unreliable, they should feel "I uploaded from the wrong angle"".
```

### What to keep in mind

The existing functionality should not be affected and it should work as is without even a 0.1% change. All the failures must be graceful in a way that the user should feel, the product is of high quality and enterprise level.


### Defect 1

The side view works perfectly fine for already tested videos. Those videos are "Good capture" side view videos. Front view video is failing with "Not Sufficient" message and "No frame available" message. But, previously for the same video, it was working as expected and the front view video looks good too. Tha video used for front view testing is front_view_squat.mp4, that is in /Users/padmakumar0930/Vectra/testing videos
