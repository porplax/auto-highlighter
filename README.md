<p align="center">
    <img align="center" src="vod-icon.svg">
</p>

<p align="center">
    CLI tool that generates clips from a video (mainly twitch VODs)
</p>

```commandline
pip install vod-highligher
```

----

- **you must have ffmpeg installed!**
- **python 3.11+**
- **free disk space of at least 2GB is recommended**

## usage
```shell
# analyzing a video and generating clips is easy!
vod-highlighter analyze -i "PATH/TO/VIDEO" 
# OR
python -m highlighter analyze -i "PATH/TO/VIDEO"
```
Use the `--help` option to see what else you can do! It is very customizable. 
## :O how does it work?!
The highlighter works by finding the loudest points of a given video. When a point 
of a video exceeds a given target dB (*default: 85.0dB*), it counts that as a 
clip and will compile that into a 30 seconds video. 

All generated videos will automatically be outputted to a directory called `./highlights`. 
This directory will be created in the location where you called the command. You can
also specifiy where the highlighter should output videos by using the `--output, -o` option.

You can also use another detection method with video! The way this method works is by
taking the brightest moments of a video and creating a clip out of that too. You can
also adjust the target luminance.

