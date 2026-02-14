# pad2noise1.0

Dependencies: numpy, sounddevice (`pip install numpy sounddevice`)
Run: `python script_name.py`

Load Files:
>LOAD POOL1 → 1st RAW file
>LOAD POOL2 → 2nd RAW file
>0-byte files are ignored by default

Mouse Controls:
>X/Y → read position, speed, step 
>Vertical acceleration → NEXT pool1
>Horizontal acceleration → NEXT pool2

Buttons:
>NEXT POOL1, NEXT POOL2 

Fixable parameters:
>Pool1 feedback = 0.05
>Pool2 feedback = 0.02 
>Low-pass cutoff = 0.1

Notes:
>RAW 8-bit PCM
