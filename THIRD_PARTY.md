# Third party components

FreeTuve relies on these upstream projects but does not vendor their full source trees.

## yt-dlp

Repository: https://github.com/yt-dlp/yt-dlp
Pinned commit: `bbc809a1161d3bfca51fa36f59dda35556ee85a0`
License: The Unlicense. See the upstream repository for the authoritative license text.

## FFmpeg

Repository: https://github.com/FFmpeg/FFmpeg
Reference commit recorded in `upstream.lock.json`: `639ee849526cfe61ceb312776335c245b98bd9d4`
License: predominantly LGPL 2.1 or later; optional build features can change the effective license. FreeTuve's Dockerfile installs the Debian packaged FFmpeg binary and does not vendor FFmpeg source.

## faster-whisper

Repository: https://github.com/SYSTRAN/faster-whisper
Pinned commit: `ed9a06cd89a93e47838f564998a6c09b655d7f43`
License: MIT. FreeTuve uses it as the local speech-to-text fallback when YouTube captions are missing or unusable. Model files are downloaded on first use into the configured model directory rather than committed to this repository.

When redistributing a packaged application, verify the licenses of the exact FFmpeg build, any enabled external libraries, the selected speech model and all transitive dependencies.
