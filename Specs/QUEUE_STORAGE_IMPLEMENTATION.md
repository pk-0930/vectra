# Azure Queue Storage Implementation

## Overview

### Current Implementation

We are polling the DB every 2 seconds from worker to check if any jobs is in need of execution but polling DB is a costly and unnecessary.

#### Drawback(s)

- Wasted Compute (almost paying for idle as container/app stays running)
- Latency (job created just after poll and worker waits for full 2 seconds so reponse time depends on poll interval)
- DB Bottleneck (unnecessary DB load at scale)
- Scaling problem using container apps/jobs (when one is processing, the next job has to wait)

### After Implementation

We are now going to leverage Event Driven with Queue Storage and Queue Trigger for azure function. So, the api would create a job in DB and push message to queue. By this way we are removing polling and the job execution happens when new job is pushed to the queue.

#### Advantages

- Zero idle cost (no job - no function running and no CPU usage, no loop)
- Lower latency (no wait and trigger immediately)
- Automatic Scaling (Scales out based on job)
- No DB polling load
- Queue is reliable with retry
- Clean Seperation
    - Polling Model -> DB = job store + job trigger
    - Queue Model -> DB = job store, Queue = job trigger


## Queue Storage Details

We are using the same Storage Account which was used for Blob Implementation but created a new Queue

Resource Group Name - "rg-vectra"
Storage Account - "vectrastorage001"
Queue Name - "analysis-jobs"
Queue URL - "https://vectrastorage001.queue.core.windows.net/analysis-jobs"
Region - "(Asia) South India"
Performance - "Standard" (Considering Cost)
Redundancy - "LRS" (Considering Cost)
Connection String - "DefaultEndpointsProtocol=https;AccountName=vectrastorage001;AccountKey=Hc2qt6LFb80DtmXCMk1cQCTFJvkeEh/8/PJaq8S5t6oGgty+GfnBhTEPofm85DOsZzXtond/zbEx+AStNXvfrg==;EndpointSuffix=core.windows.net"


## Technical Consideration

### Principles and Patterns

- Follow SOLID principles
- Implement repository pattern for Queue Client
- Connection String can be stored in a config file for now and has to be moved to keyvault in future.
- Do not overload app.py file. Maintain single responsibility principle.
- The worker must be refactored,
    - No polling to DB
    - Must be Queue triggered Azure Function (Event Driven)
- Maintain clean seperation of concern

### Security and Access

- Front End (UI) should not access Queue

### Not Considered

- KeyVault