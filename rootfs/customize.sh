#!/bin/bash
# User-facing customization of the TB138FC root filesystem (run as root in WSL).
#   sudo bash rootfs/customize.sh <mounted-rootfs-dir>      (called by mkrootfs.sh)
#   sudo bash rootfs/customize.sh                           (mounts ~/tb138fc/rootfs.img itself
#                                                            and regenerates out/rootfs.simg)
set -eo pipefail
# standalone: private mount namespace (see mkrootfs.sh)
if [ -z "$1" ] && [ -z "$TB_UNSHARED" ]; then
  exec env TB_UNSHARED=1 unshare -m --propagation private bash "$(readlink -f "$0")"
fi
source "$(dirname "$(readlink -f "$0")")/../env.sh"
WORK=/home/prizmblue/tb138fc
D2_VER=1.4.0
D2_URL=https://github.com/naver/d2-coding-font/releases/download/VER$D2_VER/D2Coding-Ver$D2_VER-20261003.zip

MNT=$1
STANDALONE=
if [ -z "$MNT" ]; then
  STANDALONE=1
  MNT=$WORK/rootfs-mnt
  mkdir -p "$MNT"
  mount -o loop "$WORK/rootfs.img" "$MNT"
  trap 'umount -l "$MNT" 2>/dev/null || true' EXIT
fi

# ---- Font: D2Coding everywhere (UI, documents, monospace, title bars, login screen) ----
mkdir -p "$WORK/dl"
ZIP=$WORK/dl/D2Coding-Ver$D2_VER.zip
[ -f "$ZIP" ] || curl -sL -o "$ZIP" "$D2_URL"
mkdir -p "$MNT/usr/share/fonts/d2coding"
bsdtar -xf "$ZIP" -C "$MNT/usr/share/fonts/d2coding" --strip-components=1 \
  "D2Coding/D2Coding-Ver$D2_VER-20261003.ttf" "D2Coding/D2CodingBold-Ver$D2_VER-20261003.ttf"
install -m 644 /dev/stdin "$MNT/usr/share/licenses/d2coding-OFL.txt" < <(bsdtar -xOf "$ZIP" OFL.txt) 2>/dev/null || true

cat > "$MNT/etc/fonts/local.conf" <<'EOF'
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<!-- D2Coding is the preferred face for every generic family; Noto fills in emoji/missing glyphs. -->
<fontconfig>
  <alias binding="strong"><family>sans-serif</family><prefer><family>D2Coding</family><family>Noto Color Emoji</family></prefer></alias>
  <alias binding="strong"><family>serif</family><prefer><family>D2Coding</family><family>Noto Color Emoji</family></prefer></alias>
  <alias binding="strong"><family>monospace</family><prefer><family>D2Coding</family><family>Noto Color Emoji</family></prefer></alias>
  <alias binding="strong"><family>system-ui</family><prefer><family>D2Coding</family></prefer></alias>
</fontconfig>
EOF

# GNOME defaults for users and for GDM (dconf system databases)
mkdir -p "$MNT/etc/dconf/profile" "$MNT/etc/dconf/db/local.d" "$MNT/etc/dconf/db/gdm.d"
printf 'user-db:user\nsystem-db:local\n' > "$MNT/etc/dconf/profile/user"
printf 'user-db:user\nsystem-db:gdm\nfile-db:/usr/share/gdm/greeter-dconf-defaults\n' > "$MNT/etc/dconf/profile/gdm"
for db in local gdm; do
  cat > "$MNT/etc/dconf/db/$db.d/00-tb138fc-fonts" <<'EOF'
[org/gnome/desktop/interface]
font-name='D2Coding 11'
document-font-name='D2Coding 11'
monospace-font-name='D2Coding 11'

[org/gnome/desktop/wm/preferences]
titlebar-font='D2Coding Bold 11'
EOF
done

chroot "$MNT" /bin/sh -c 'fc-cache -f >/dev/null && dconf update && fc-match sans-serif && fc-match monospace'

if [ -n "$STANDALONE" ]; then
  umount "$MNT"; trap - EXIT
  e2fsck -fy "$WORK/rootfs.img" >/dev/null || true
  img2simg "$WORK/rootfs.img" "$OUT/rootfs.simg"
  ls -l "$OUT/rootfs.simg"
fi
echo "CUSTOMIZE DONE"
