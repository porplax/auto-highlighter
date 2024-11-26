<p align="center">
    <img align="center" src="https://i.ibb.co/bJ1svtq/simplified-icon.png">
</p>

<div align="center">

# ⚡auto-highlighter⚡

</div>

![example](https://i.postimg.cc/yNd9GXKf/Animation.gif)

```commandline
pip install auto-highligher-py
```

----

`auto-highlighter` is a tool I developed to assist in video editing. It looks through hours of a
video for you and finds any clips that can be used for a TikTok or editing.

As an editor for multiple streamers, I am often tasked with having to look through
hours of content to find a clip to create a TikTok from. So this tool gets the job done in
minutes.

![demo.gif](https://i.postimg.cc/Cx0GWLf2/demo.gif)

It saves detected clips to a folder for you to look through. By default, it is the `highlights` folder.

# use cases

With this tool, you can easily find clips that otherwise would've taken hours.
It can:

- Automatically detect any possible clips by audio / video.
- Save these clips to a folder for manual review.
- The clips will be in the original resolution as the VOD.
- Length of these clips can be customized.
- Can generate from any format.

# installation

To begin using this project you must have the following installed
onto your machine.

1. [FFmpeg](https://www.ffmpeg.org/download.html) should be installed and on `PATH`. (*preferably version 7.0.0+*)
2. [Python](https://www.python.org/downloads/release/python-31110/) 3.11+

On Windows, open the start menu and type in `cmd` and open it.
Linux users can open their terminal by doing `CTRL+ALT+T` or by finding it.
I don't own a macbook 💀

Once installed, verify that you can call each command from
your terminal.

Then using `pip`, install `auto-highlighter`.

```shell
> pip install auto-highlighter-py
```

```shell
> python --version 
'python 3.11.9' # or similar.
> ffmpeg -version
'ffmpeg version <version>-<build>...'
```

**2 gigabytes** of space is recommended.

# usage

```shell
 Usage: python -m highlighter [OPTIONS] COMMAND [ARGS]...

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.                                              │
│ --show-completion             Show completion for the current shell, to copy it or customize the installation.       │
│ --help                        Show this message and exit.                                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ analyze          analyze VOD for any highlights.                                                                     │
│ reference   find average decibel in video. (if you re unsure what target decibel to aim for, use this)          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

```shell
# analyzing a video and generating clips is easy!
> auto-highlighter analyze -i "PATH/TO/VIDEO" 
# OR
> python -m highlighter analyze -i "PATH/TO/VIDEO"
```

Whenever the tool begins analyzing, it will place all generated clips in `highlights` folder, or
in the folder you set the highlighter to place the clips at.
Use the `--help` option to see what else you
can do! It is very customizable.

### adjusting to get the best results

`auto-highlighter` will highlight moments of a given VOD based on how loud a specific point in the video is. By default, It is set to `85.0dB` and if a moment goes past this value it will be highlighted.  

However this is different across each video. So if needed, you can adjust the target decibel using `-t <DECIBEL>` option. If you don't know what target decibel to aim for, using the `reference` command will give you information about the average decibel of the video, and the greatest decibel found.

```shell
# find a target decibel
auto-highligher reference "PATH/TO/VIDEO"
# OR
python -m highlighter reference "PATH/TO/VIDEO"
```

**TL:DR:** *use this command if the highlighter is creating too many, or too little clips. this will tell you the recommended target decibel to set.*

---

## :O how does it work?

The highlighter works by finding the loudest points of a given video. When a point  
of a video exceeds a given target dB (*default: 85.0dB*), it counts that as a  
clip and will compile that into a 30 seconds video.  

All generated videos will automatically be outputted to a directory called `./highlights`.  
This directory will be created in the location where you called the command. You can
also specifiy where the highlighter should output videos by using the `--output, -o` option.

You can also use another detection method with video! The way this method works is by
taking the brightest moments of a video and creating a clip out of that too. You can
also adjust the target luminance.

## the tech behind it

**Python 3.11+, Poetry (Package Management), FFMpeg (Video Conversion, and Generation)**

Python is the programming language of choice for this project. It was very simple
to use and allowed me to make this software very quickly. Poetry is used to easily
publish this package to PyPI and use it in a virtual environment. FFMpeg is used
on the command line to convert video to audio (*for analysis*) and to generate
clips from highlights.

## to-do

- [X] Optimize decibel algorithm.
- [X] Implement threading for clip generation.
- [ ] Add `watch` function, which can be used to create clips from ongoing streams.