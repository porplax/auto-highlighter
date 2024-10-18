<p align="center">
    <img align="center" src="https://i.ibb.co/bJ1svtq/simplified-icon.png">
</p>

<p align="center">
    automatically generate clips from VODs!
</p>

![example](https://i.postimg.cc/yNd9GXKf/Animation.gif)

```commandline
pip install auto-highligher-py
```

----

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

```shell
> python --version 
'python 3.11.9' # or similar.
> ffmpeg -version
'ffmpeg version <version>-<build>...'
```

**2 gigabytes** of space is recommended.

# usage

```shell
# analyzing a video and generating clips is easy!
auto-highlighter analyze -i "PATH/TO/VIDEO" 
# OR
python -m highlighter analyze -i "PATH/TO/VIDEO"
```

Whenever the tool begins analyzing, it will place all generated clips in Use the `--help` option to see what else you
can do! It is very customizable.

### adjusting to get the best results

`auto-highlighter` will highlight moments of a given VOD based on how loud a specific point in the video is. By default, It is set to `85.0dB` and if a moment goes past this value it will be highlighted.  

However this is different across each video. So if needed, you can adjust the target decibel using `-t <DECIBEL>` option. If you don't know what target decibel to aim for, using the `find-reference` command will give you information about the average decibel of the video, and the greatest decibel found.

```shell
# find a target decibel
auto-highligher find-reference -i "PATH/TO/VIDEO"
# OR
python -m highlighter find-reference -i "PATH/TO/VIDEO"
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

- [ ] Optimize decibel algorithm.
- [ ] Implement threading for clip generation.
- [ ] Add `watch` function, which can be used to create clips from ongoing streams.

### ML-Based clip detection (AI)

Using Machine Learning as a means of clip detection can be done. Using my clips and it's luminance and wave data as a means of clip detection. May do this soon.

## roadmap

- [ ] I am currently switching to rust as an alternative!
- [ ] GUI support is on the way.
- [ ] Documentation.
