# 💬 Teleconsult Feature Specification

## 🎯 Goal
Enable direct communication between patients and nurses with:
- Issue categorization
- Queue management
- Office hours handling
- Priority routing
- Session tracking

---

## 📋 Feature Breakdown

### Phase 1: Basic Contact (Current - 30%)
- ✅ Rich Menu button exists
- ❌ No functionality yet

### Phase 2: Smart Contact System (Target - 100%)
- ✅ Issue categorization
- ✅ Queue management
- ✅ Office hours check
- ✅ Priority routing
- ✅ Session tracking
- ✅ Nurse assignment

---

## 🏗️ Architecture

```
User → Dialogflow Intent "ContactNurse"
  ↓
Categorize Issue
  ↓
Check Office Hours
  ↓
  ├─ During Hours → Check Nurse Availability
  │   ├─ Available → Direct Connect
  │   └─ Busy → Add to Queue
  │
  └─ After Hours → Emergency Check
      ├─ Emergency → Alert On-Call Nurse
      └─ Non-Emergency → Schedule Next Day
```

---

## 💬 User Flows

### Flow 1: Normal Contact (Office Hours)
```
User: "ปรึกษาพยาบาล"

Bot: "สวัสดีค่ะ เลือกเรื่องที่ต้องการปรึกษา:
     1. ⚠️ อาการฉุกเฉิน
     2. 💊 ถามเรื่องยา
     3. 🩹 แผลผ่าตัด
     4. 📋 นัดหมาย/เอกสาร
     5. ❓ อื่นๆ"

User: "3"

Bot: "เข้าใจแล้วค่ะ เรื่องแผลผ่าตัด
     
     📊 ตำแหน่งในคิว: 2
     ⏱️ เวลารอโดยประมาณ: 10-15 นาที
     
     พยาบาลจะติดต่อกลับโดยเร็วนะคะ
     หรือพิมพ์ 'ยกเลิก' เพื่อยกเลิก"

[System saves to queue, alerts nurse]

Nurse: [Responds via LINE]

Bot: "✅ พยาบาลตอบกลับแล้วค่ะ"
```

### Flow 2: Emergency (Any Time)
```
User: "ปรึกษาพยาบาล"
User: "1" (emergency)

Bot: "🚨 เข้าใจค่ะ นี่เป็นเรื่องฉุกเฉิน
     
     กรุณาอธิบายอาการโดยสังเขป:"

User: "เลือดออกจากแผลไม่หยุด"

Bot: "📞 กำลังติดต่อพยาบาลด่วน...
     
     ⚠️ ถ้าอาการรุนแรงมาก โปรดโทร 1669
     
     พยาบาลจะติดต่อกลับภายใน 5 นาที"

[System: Priority alert to on-call nurse]
```

### Flow 3: After Office Hours (Non-Emergency)
```
User: "ปรึกษาพยาบาล" (sent at 22:00)

Bot: "สวัสดีค่ะ 😊
     
     ⏰ ขณะนี้นอกเวลาทำการ (เวลา 22:00)
     เวลาทำการ: 8:00-18:00 น.
     
     📌 คำถามของคุณสำคัญมากไหมคะ?
     
     1. 🚨 ฉุกเฉิน (ติดต่อเจ้าหน้าที่เวร)
     2. 📝 ไม่เร่งด่วน (บันทึกไว้ติดต่อพรุ่งนี้)"

User: "2"

Bot: "รับทราบค่ะ กรุณาอธิบายเรื่องที่ต้องการปรึกษา:"

User: "อยากถามเรื่องยาที่ทาน"

Bot: "✅ บันทึกแล้วค่ะ
     
     พยาบาลจะติดต่อกลับพรุ่งนี้
     ในเวลา 9:00-10:00 น.
     
     🙏 ขอบคุณค่ะ"
```

---

## 🗄️ Database Schema

### New Sheet: TeleconsultSessions

| Column | Type | Description |
|--------|------|-------------|
| Session_ID | String | Unique session ID |
| Timestamp | Datetime | When created |
| User_ID | String | Patient's LINE ID |
| Issue_Type | String | Category (emergency, medication, wound, appointment, other) |
| Priority | String | high, medium, low |
| Status | String | queued, in_progress, completed, cancelled |
| Description | Text | User's description |
| Queue_Position | Integer | Position in queue |
| Assigned_Nurse | String | Nurse ID (if assigned) |
| Started_At | Datetime | When nurse responded |
| Completed_At | Datetime | When session ended |
| Notes | Text | Internal notes |

### New Sheet: TeleconsultQueue

| Column | Type | Description |
|--------|------|-------------|
| Queue_ID | String | Unique queue ID |
| Timestamp | Datetime | When added to queue |
| Session_ID | String | Reference to session |
| User_ID | String | Patient's LINE ID |
| Issue_Type | String | Category |
| Priority | Integer | 1=high, 2=med, 3=low |
| Status | String | waiting, assigned, removed |
| Estimated_Wait | Integer | Minutes |

---

## ⚙️ Configuration

```python
# Office Hours
OFFICE_HOURS = {
    'start': '08:00',
    'end': '18:00',
    'days': [0, 1, 2, 3, 4]  # Mon-Fri
}

# Issue Categories
ISSUE_CATEGORIES = {
    'emergency': {'priority': 1, 'icon': '🚨', 'max_wait': 5},
    'medication': {'priority': 2, 'icon': '💊', 'max_wait': 15},
    'wound': {'priority': 2, 'icon': '🩹', 'max_wait': 15},
    'appointment': {'priority': 3, 'icon': '📋', 'max_wait': 30},
    'other': {'priority': 3, 'icon': '❓', 'max_wait': 30}
}

# Queue Settings
MAX_QUEUE_SIZE = 10
NURSE_RESPONSE_TIMEOUT = 30  # minutes
```

---

## 🔔 Notifications

### To Nurse (New Request):
```
🔔 คำขอปรึกษาใหม่

👤 ผู้ป่วย: user_abc123
📋 ประเภท: 🩹 แผลผ่าตัด
⚠️ ระดับ: กลาง
💬 รายละเอียด: "แผลบวมเล็กน้อย"

📊 คิวปัจจุบัน: 2 คน
⏱️ เวลารอ: 10-15 นาที

[รับเคส] [มอบหมาย] [ดูโปรไฟล์]
```

### To User (Nurse Response):
```
✅ พยาบาลตอบกลับแล้วค่ะ

💬 คำตอบจากพยาบาล:
"แผลบวมเล็กน้อยเป็นเรื่องปกติค่ะ 
แต่ถ้าบวมมากขึ้นหรือมีไข้ 
กรุณารีบมาโรงพยาบาลนะคะ"

🙏 พอใจกับการบริการไหมคะ?
[⭐⭐⭐⭐⭐]
```

---

## 🎨 Rich Menu Updates

### Current Button:
```
ปรึกษาพยาบาล
[No action]
```

### Updated Action:
```
Text: "ปรึกษาพยาบาล"
→ Triggers Dialogflow Intent: ContactNurse
```

---

## 🧪 Test Cases

### Test 1: Normal Contact (Office Hours)
```
Time: 10:00 (weekday)
User: "ปรึกษาพยาบาล"
Expected: Show categories, add to queue
```

### Test 2: Emergency Contact
```
User: Select "ฉุกเฉิน"
Expected: Priority alert to nurse, skip queue
```

### Test 3: After Hours (Non-Emergency)
```
Time: 20:00
User: Non-emergency issue
Expected: Schedule for next day
```

### Test 4: Queue Management
```
User 1: Request (10:00)
User 2: Request (10:01)
User 3: Request (10:02)
Expected: Queue positions 1, 2, 3
```

### Test 5: Nurse Response
```
Nurse: Responds to request
Expected: Notify user, update status, remove from queue
```

---

## 📊 Analytics to Track

- Total consultations per day
- Average wait time
- Response rate
- Issue type distribution
- Peak hours
- Satisfaction scores

---

## 🚀 Implementation Plan

### Phase 1: Core System (Days 1-3)
- Create database schemas
- Implement issue categorization
- Build queue management
- Add session tracking

### Phase 2: Smart Features (Days 4-5)
- Office hours checking
- Priority routing
- Nurse assignment logic

### Phase 3: Notifications (Day 6)
- Nurse alerts
- User confirmations
- Queue updates

### Phase 4: Polish & Test (Day 7)
- Error handling
- Edge cases
- User testing
- Documentation

**Total Time: 7 days** ⏱️

---

## 💡 Key Features

### 1. Smart Routing
- Emergency → Immediate alert
- Non-emergency → Queue
- After hours → Schedule next day

### 2. Queue Management
- Position tracking
- Estimated wait time
- Priority ordering

### 3. Session Tracking
- Full conversation history
- Status updates
- Completion tracking

### 4. Nurse Dashboard (Future)
- View queue
- Assign cases
- Track performance

---

## 🎯 Success Metrics

- ✅ Average response time < 15 min
- ✅ 90% of requests handled within office hours
- ✅ User satisfaction > 4.0/5.0
- ✅ Zero missed emergency requests

---

**Ready to implement?** Let's code! 🚀
