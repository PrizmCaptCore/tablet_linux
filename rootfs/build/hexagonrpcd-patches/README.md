Registry write support for hexagonrpcd, from the Galaxy Tab S8+ port
(https://github.com/aaronsb/sm-x800-linux, pmaports-overlay/temp/hexagonrpcd, PR #37;
queued upstream as https://github.com/linux-msm/hexagonrpc/issues/19 and PR #21).
They apply to hexagonrpc commit 598b591ae9da6a6cfe2ca5ea78998019ca6395ea.

The TB138FC SLPI also rewrites its registry while it initialises (temp.json next to the
registry, sns_reg_version). Stock hexagonrpcd refuses every write, the SLPI retries forever and
never registers the SPI-attached accelerometer. With DIR/sensors/persist/registry present the
patched daemon serves that directory read-write as /persist/sensors/registry.
