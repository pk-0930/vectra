# Azure Blob Storage Implementation

## Overview

We are now using local storage for storing the uploaded videos, extracted frames and annotated output frames in `uploads`, `frames` and `outputs/frames` folders respectively. This is not scalable and so we are introducing blob storage for storing those files.

After the blob implementation, no local storage will be used and everything will be blob based.

## Storage Account Details

Resource Group Name - "rg-vectra"
Storage Account - "vectrastorage001"
Region - "(Asia) South India"
Performance - "Standard" (Considering Cost)
Redundancy - "LRS" (Considering Cost)
Connection String - "DefaultEndpointsProtocol=https;AccountName=vectrastorage001;AccountKey=Hc2qt6LFb80DtmXCMk1cQCTFJvkeEh/8/PJaq8S5t6oGgty+GfnBhTEPofm85DOsZzXtond/zbEx+AStNXvfrg==;EndpointSuffix=core.windows.net"

### Blob Container details mapping to local folder

uploads (local folder) -> uploads (Container)
frames (local folder) -> frames (Container)
outputs/frames (local folder) -> annotated-frames (Container)

## Technical Considerations

- Follow Solid Principles.
- Prefer repository or any relevant pattern for Blob Client.
- Connection String can be stored in a config file for now and has to be moved to keyvault in future.
- Do not overload app.py file. Maintain single responsibility principle.
- Front End (UI) should not access blob by itself, it should always use the backend api to post or get any files from blob if necessary.

## TODO 

### Task 1 - Performance Improvement

UI upload to backend processing to annotated frames response feels slower from front perspective.

- Extracted frames does not have to be uploaded to blob, instead can be stored in temp location in memory and can be deleted after execution. We do not want extrated frames for future use.
- The original video and annotated frames go to blob
- Remove "frames" container from blob storage

### Task 2 - Security Improvement

- Temporary access URL using SAS.
- No KeyVault.


