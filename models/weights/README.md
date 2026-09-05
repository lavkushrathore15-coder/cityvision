# Model Weights Directory

This directory holds serialized deep learning weights for local model inference.

### Required Model Artifacts
1. **Vehicle Detector**:
   - `yolov8n.pt` or `yolov8s.pt` (Ultralytics PyTorch / ONNX)
   - Classes detected: `car`, `motorcycle`, `bus`, `truck` (COCO class IDs: 2, 3, 5, 7)

2. **License Plate Detector**:
   - `plate_detector.pt` / `plate_detector.onnx`
   - Single-class bounding box detector for vehicle license plates.

3. **ANPR Text Recognition**:
   - PaddleOCR / ONNX recognition weights or EasyOCR weights.

4. **Vehicle Re-ID Embedding Extractor**:
   - `osnet_x0_25.onnx` or `osnet_ain_x1_0.onnx` (Vehicle Re-ID trained on VeRi-776 or VehicleID)
   - Outputs 512-dimensional normalized embedding vector per vehicle crop.
