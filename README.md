# ♻️ EcoSort AI

> ระบบปัญญาประดิษฐ์เพื่อจำแนก ตรวจสอบคุณภาพ และแนะนำการจัดการขยะรีไซเคิลอย่างอัจฉริยะ

CS461 Final Project — ระบบ AI ที่ใช้ Deep Learning 2 โมเดล (YOLO + CNN) สำหรับตรวจจับขยะ จำแนกประเภท ตรวจสอบคุณภาพ และแนะนำการจัดการขยะ พร้อม Dashboard วิเคราะห์ข้อมูลสำหรับชุมชน

---

## 📋 สารบัญ

1. [ภาพรวมระบบ](#-ภาพรวมระบบ)
2. [โมดูลระบบ](#-โมดูลระบบ)
3. [สถาปัตยกรรม AI](#-สถาปัตยกรรม-ai)
4. [โครงสร้างโปรเจกต์](#-โครงสร้างโปรเจกต์)
5. [การติดตั้งและรัน](#-การติดตั้งและรัน)
6. [การฝึกโมเดล](#-การฝึกโมเดล)
7. [API Reference](#-api-reference)
8. [Dataset](#-dataset)
9. [แผนการทดลอง](#-แผนการทดลอง)

---

## 🔍 ภาพรวมระบบ

EcoSort AI แก้ปัญหาการคัดแยกขยะในโรงเรียน ชุมชน และศูนย์รับซื้อวัสดุรีไซเคิล โดย:

- ตรวจจับและจำแนกประเภทขยะจากภาพถ่าย (พลาสติก กระดาษ กระดาษลัง แก้ว โลหะ ขยะทั่วไป)
- ตรวจสอบสภาพขยะว่าสะอาดหรือมีสิ่งปนเปื้อน
- ให้คำแนะนำการจัดการขยะเชิงปฏิบัติ
- วิเคราะห์ข้อมูลและแสดงสถิติผ่าน Dashboard

**กลุ่มผู้ใช้งาน:** โรงเรียน ชุมชน ธนาคารขยะ และศูนย์คัดแยกขยะ

---

## 📦 โมดูลระบบ

| โมดูล | ฟังก์ชัน | เทคโนโลยี |
|-------|---------|----------|
| **1. AI ตรวจจับและจำแนกขยะ** | อัปโหลดภาพ → ตรวจจับ Bounding Box → จำแนกประเภท → แสดงค่าความมั่นใจ | YOLOv8 |
| **2. AI ตรวจสอบคุณภาพ** | ตรวจสอบขยะสะอาด/ปนเปื้อน → ให้คำแนะนำ | CNN (ResNet18) |
| **3. ระบบแนะนำการจัดการขยะ** | แนะนำถังขยะ → วิธีเตรียมขยะ → การจัดการขยะที่ไม่รีไซเคิลได้ | Rule-based Engine |
| **4. Dashboard วิเคราะห์ข้อมูล** | สถิติตามประเภท → รายวัน/สัปดาห์/เดือน → แนวโน้ม → ส่งออกรายงาน | Chart.js |

---

## 🧠 สถาปัตยกรรม AI

```
ผู้ใช้อัปโหลดภาพขยะ
        │
        ▼
┌─────────────────────┐
│  Model 1: YOLO     │  ตรวจจับวัตถุ + Bounding Box + จำแนกประเภท
│  (Object Detection) │  ผลลัพธ์: ตำแหน่ง, ประเภท, ค่าความมั่นใจ
└────────┬────────────┘
         │ Crop วัตถุแต่ละชิ้น
         ▼
┌─────────────────────┐
│  Model 2: CNN      │  จำแนกสภาพ สะอาด / ปนเปื้อน
│  (Classification)    │  ผลลัพธ์: คุณภาพ, ค่าความมั่นใจ
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Recommendation     │  ประมวลผลคำแนะนำจาก ประเภท + คุณภาพ
│  Engine             │  ผลลัพธ์: ถังขยะ, วิธีเตรียม, การจัดการ
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Web App + Dashboard│  แสดงผล, บันทึก, วิเคราะห์สถิติ
└─────────────────────┘
```

### โหมดการทำงานของ AI

ระบบทำงานได้ใน 3 ระดับ ตามโมเดลที่มี:

| โหมด | YOLO | CNN | คำอธิบาย |
|------|------|-----|---------|
| **Custom** | ✅ โมเดลที่ฝึกเอง | ✅ โมเดลที่ฝึกเอง | ใช้หลังจาก Train แล้ว (ความแม่นยำสูงสุด) |
| **Pre-trained** | ✅ YOLOv8 COCO | ⚠️ Heuristic | ใช้ได้ทันทีหลังติดตั้ง dependencies |
| **Demo** | ⚠️ Mock detection | ⚠️ Mock classification | ทำงานได้โดยไม่ต้องติดตั้ง torch/ultralytics |

> 💡 ระบบจะเลือกโหมดที่ดีที่สุดที่มีอัตโนมัติ ไม่ต้องตั้งค่าเพิ่มเติม

---

## 📁 โครงสร้างโปรเจกต์

```
EcoSortAI/
├── app.py                      # Flask application (main entry point)
├── config.py                   # Configuration (DB, uploads, model paths)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
│
├── models/                     # Python package: AI + Database models
│   ├── __init__.py
│   ├── database.py             # SQLAlchemy models (ScanRecord, DetectedItem)
│   ├── waste_detection.py      # YOLO object detection wrapper
│   ├── quality_classifier.py   # CNN quality classifier
│   ├── recommendation.py       # Rule-based recommendation engine
│   └── weights/                # Trained model weights (auto-created)
│
├── training/                   # Training scripts
│   ├── prepare_dataset.py      # Dataset preparation (splits + YOLO format)
│   ├── train_yolo.py           # YOLO training (Exp 1, 3, 4)
│   └── train_cnn.py            # CNN training (Exp 2, 3, 4, 5)
│
├── templates/                  # Jinja2 HTML templates
│   ├── base.html               # Base template (nav + footer)
│   ├── index.html              # Home page
│   ├── scanner.html            # AI Scanner (Modules 1-3)
│   ├── dashboard.html          # Analytics Dashboard (Module 4)
│   └── about.html              # About page
│
├── static/
│   ├── css/style.css           # All styling
│   ├── js/
│   │   ├── main.js             # Shared utilities
│   │   ├── scanner.js          # Scanner page logic
│   │   └── dashboard.js        # Dashboard charts (Chart.js)
│   └── uploads/                # Uploaded images (auto-created)
│
└── data/                       # Database + datasets (auto-created)
    └── ecosort.db               # SQLite database
```

---

## 🚀 การติดตั้งและรัน

### ข้อกำหนด

- Python 3.9+
- pip

### ขั้นตอนที่ 1: ติดตั้ง dependencies

```bash
cd EcoSortAI
pip install -r requirements.txt
```

> ⚠️ การติดตั้ง PyTorch บางเครื่องอาจต้องระบุเวอร์ชันตาม CUDA
> ดูคำแนะนำได้ที่ https://pytorch.org/get-started/locally/

### ขั้นตอนที่ 2: รันแอปพลิเคชัน

```bash
python app.py
```

### ขั้นตอนที่ 3: เปิดเบราว์เซอร์

```
http://localhost:5000
```

> 💡 แอปพลิเคชันทำงานได้ทันทีแม้ยังไม่ได้ Train โมเดล
> ระบบจะใช้ Pre-trained หรือ Heuristic mode อัตโนมัติ

---

## 🎓 การฝึกโมเดล

### ขั้นตอนที่ 1: เตรียม Dataset

```bash
# ดาวน์โหลด TrashNet และ RealWaste จากแหล่งข้อมูลที่ระบุ
# จัดโครงสร้าง:
#   datasets/
#     trashnet/
#       glass/  paper/  plastic/  cardboard/  metal/  trash/
#     realwaste/
#       cardboard/  food_organics/  glass/  metal/  ...

# เตรียม dataset สำหรับ YOLO
python training/prepare_dataset.py --mode yolo --source datasets/ --output data/yolo_dataset

# เตรียม dataset สำหรับ CNN (รวบรวมภาพสะอาด/ปนเปื้อนเอง)
python training/prepare_dataset.py --mode cnn --source quality_images/ --output data/cnn_dataset
```

### ขั้นตอนที่ 2: Train YOLO (Experiment 1)

```bash
# Train พื้นฐาน
python training/train_yolo.py --data data/yolo_dataset/data.yaml --epochs 100

# ทดลอง Learning Rate และ Batch Size (Experiment 4)
python training/train_yolo.py --data data/yolo_dataset/data.yaml --lr 0.01 --batch 32

# เปรียบเทียบ Optimizer: Adam vs SGD (Experiment 3)
python training/train_yolo.py --data data/yolo_dataset/data.yaml --compare-optimizers --epochs 50
```

### ขั้นตอนที่ 3: Train CNN (Experiment 2)

```bash
# Train พื้นฐาน
python training/train_cnn.py --data data/cnn_dataset --epochs 50

# ทดลอง Dropout และ Early Stopping (Experiment 5)
python training/train_cnn.py --data data/cnn_dataset --dropout 0.5 --patience 15

# เปรียบเทียบ Optimizer (Experiment 3)
python training/train_cnn.py --data data/cnn_dataset --compare-optimizers --epochs 30
```

### ผลลัพธ์การ Train

- โมเดลที่ดีที่สุดจะถูกบันทึกที่ `models/weights/yolo_waste.pt` และ `models/weights/cnn_quality.pth`
- ผลการทดลอง (metrics) จะถูกบันทึกเป็น JSON ในโฟลเดอร์ `training/`
- หลังจาก Train เสร็จ รีสตาร์ท `app.py` และระบบจะใช้โมเดลที่ฝึกแล้วอัตโนมัติ

---

## 🔗 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | หน้าแรก |
| GET | `/scanner` | หน้า AI Scanner |
| GET | `/dashboard` | หน้า Dashboard |
| GET | `/about` | หน้าข้อมูลโครงงาน |
| POST | `/api/scan` | อัปโหลดภาพและประมวลผล AI |
| POST | `/api/save` | บันทึกผลการสแกนลงฐานข้อมูล |
| GET | `/api/scans` | ดึงประวัติการสแกน |
| GET | `/api/scans/<id>` | ดึงรายละเอียดการสแกน |
| GET | `/api/stats` | สถิติสรุปสำหรับ Dashboard |
| GET | `/api/trends?period=daily` | ข้อมูลแนวโน้ม (daily/weekly/monthly) |
| GET | `/api/category-trends` | คุณภาพขยะแยกตามประเภท |
| GET | `/api/export` | ส่งออกข้อมูลเป็น CSV |
| GET | `/api/model-status` | สถานะโมเดล AI |

---

## 📊 Dataset

| Dataset | ใช้สำหรับ | ขนาด | แหล่งข้อมูล |
|---------|---------|------|-----------|
| TrashNet | จำแนกประเภทขยะ | 2,527 ภาพ, 6 ประเภท | GitHub |
| RealWaste | เพิ่มภาพสภาพแวดล้อมจริง | 4,752 ภาพ, 9 ประเภท | UCI ML Repository |
| ภาพสิ่งปนเปื้อน (รวบรวมเอง) | ตรวจสอบคุณภาพ | 300-500 ภาพ/สถานะ | ทีมรวบรวม |

> ⚠️ TrashNet และ RealWaste ไม่มี Label สิ่งปนเปื้อน ต้องติด Label เพิ่มสำหรับ CNN

---

## 🧪 แผนการทดลอง

| # | การทดลอง | คำสั่ง |
|---|---------|-------|
| 1 | Train YOLO | `train_yolo.py --epochs 100` |
| 2 | Train CNN | `train_cnn.py --epochs 50` |
| 3 | เปรียบเทียบ Optimizer | `--compare-optimizers` |
| 4 | Learning Rate + Batch Size | `--lr 0.01 --batch 32` |
| 5 | Dropout + Early Stopping | `--dropout 0.5 --patience 15` |
| 6 | ประเมินผล (Test Set) | อัตโนมัติหลัง Train |

### ตัวชี้วัดที่รายงาน

- **YOLO:** Precision, Recall, mAP@50, mAP@50-95
- **CNN:** Accuracy, Precision, Recall, F1-score, Confusion Matrix
- **Training:** Training Loss, Validation Loss (บันทึกใน history)
- **ระบบโดยรวม:** เวลาประมวลผลต่อภาพ, ความถูกต้องของคำแนะนำ

---

## 🛠️ เทคโนโลยี

| ส่วนระบบ | เทคโนโลยี |
|---------|----------|
| AI Object Detection | Python + YOLOv8 (ultralytics) |
| AI Image Classification | Python + PyTorch (ResNet18) |
| Image Processing | OpenCV |
| Backend | Flask |
| Frontend | HTML, CSS, JavaScript |
| Database | SQLite (เปลี่ยนเป็น MySQL ได้ที่ config.py) |
| Dashboard | Chart.js |

---

## 📝 License

CS461 Final Project — Educational use

## Smart Waste Action Planner + Recovery (new)

สแกน → วางแผน → ลงมือทำ → สแกนซ้ำ/ยืนยัน → สรุปผลใน Dashboard

- หน้า `/waste-planner` เลือกประวัติสแกนที่บันทึกแล้ว สร้างแผนและรายการงาน (ต้องเข้าสู่ระบบ)
- หน้า `/waste-recovery` ติดตามงาน: `pending → in_progress → awaiting_review → completed | unable`
- สแกนซ้ำเป็นหลักฐานประกอบ ผู้ใช้ต้องยืนยันผลเอง ถ้าผลสแกนซ้ำไม่ตรงจะบันทึก `mismatch` (ไม่แก้ข้อมูลเดิม)
- ได้คะแนนเมื่องานถูกยืนยัน (+10 กู้ขยะปนเปื้อน / +3 งานอื่น) ครั้งเดียวต่องาน
- ตารางใหม่ `waste_action_plans`, `plan_tasks` ถูกสร้างอัตโนมัติด้วย `db.create_all()` ไม่กระทบข้อมูลเดิม
- API: `/api/my-scans`, `/api/plans` (GET/POST/PATCH/DELETE), `/api/recovery/tasks`, `.../start|complete|rescan|verify`, `/api/recovery/stats`
