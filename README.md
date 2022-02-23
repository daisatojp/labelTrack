# labelTrack

In visual tracking dataset, a sequence of images has one object for each image, in contrast to object detection dataset that has multiple objects in each image. This annotation tool is suited for that.

## Quick Start

```bash
git clone https://github.com/daisatojp/labelTrack.git
cd labelTrack
pip install pyqt5==5.14.1
python labelTrack.py
```

* Click `Open Label File` in toolbar to select label file to be saved.
* Click `Open Image Dir` in toolbar to open a folder containing a sequence of images.
* Click `Create Object` in toolbar and make box by a mouse dragging in each image.
* Click `Save` in toolbar to save label file.

## Useful Shortcuts

| Key | Action |
| --- | --------------- |
| `d` | open next image |
| `a` | open previous image |
| `w` | create bounding box |
| `c` | remove bounding box |
| `r` | copy bounding box from previous image |
| `t` | open next image and copy bounding box from previous image |
| `v` | open next image and remove bounding box |

## Acknowledgment

* [labelimg](https://github.com/tzutalin/labelImg) as a reference
* 
