#!/bin/bash
# Download person detection models for Pulse 1.0

MODELS_DIR="/opt/pulse/models"
mkdir -p "$MODELS_DIR"

echo "Downloading person detection models..."

# MobileNet SSD prototxt (always download - small file)
if [ ! -f "$MODELS_DIR/MobileNetSSD_deploy.prototxt" ]; then
    echo "Downloading MobileNet SSD prototxt..."
    wget -q -O "$MODELS_DIR/MobileNetSSD_deploy.prototxt" \
        https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt
fi

# MobileNet SSD model (optional - large file ~20MB)
if [ ! -f "$MODELS_DIR/MobileNetSSD_deploy.caffemodel" ]; then
    echo "Downloading MobileNet SSD model (20MB)..."
    wget -q --show-progress -O "$MODELS_DIR/MobileNetSSD_deploy.caffemodel" \
        https://github.com/chuanqi305/MobileNet-SSD/raw/master/MobileNetSSD_deploy.caffemodel || true
fi

# YOLOv3 config (optional)
if [ ! -f "$MODELS_DIR/yolov3.cfg" ]; then
    echo "Downloading YOLOv3 config..."
    wget -q -O "$MODELS_DIR/yolov3.cfg" \
        https://raw.githubusercontent.com/pjreddie/darknet/master/cfg/yolov3.cfg || true
fi

# COCO class names (for YOLO)
if [ ! -f "$MODELS_DIR/coco.names" ]; then
    echo "Downloading COCO class names..."
    wget -q -O "$MODELS_DIR/coco.names" \
        https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names || true
fi

echo "Model download complete!"
echo "Note: YOLOv3 weights (237MB) not downloaded. Download manually if needed:"
echo "  wget -O $MODELS_DIR/yolov3.weights https://pjreddie.com/media/files/yolov3.weights"

# Set permissions
chown -R pi:pi "$MODELS_DIR" 2>/dev/null || true
