# -*- coding: utf-8 -*-
"""
Configuration Module
Centralized configuration management for KwanNurse-Bot
"""
import os
import logging
from zoneinfo import ZoneInfo

# Application Configuration
DEBUG = os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes")
PORT = int(os.environ.get("PORT", 5000))

# Timezone
LOCAL_TZ = ZoneInfo("Asia/Bangkok")

# Google Sheets Configuration
WORKSHEET_LINK = os.environ.get(
    "WORKSHEET_LINK",
    "https://docs.google.com/spreadsheets/d/1Jteh4XLzgQM3YKMzUeW3PGuBjUkvnS61rm2IXfGPnPo/edit?usp=sharing"
)
GSPREAD_CREDENTIALS = os.environ.get("GSPREAD_CREDENTIALS")
SPREADSHEET_NAME = "KhwanBot_Data"

# Sheet Names
SHEET_SYMPTOM_LOG = "SymptomLog"
SHEET_RISK_PROFILE = "RiskProfile"
SHEET_APPOINTMENTS = "Appointments"
SHEET_FOLLOW_UP_REMINDERS = "FollowUpReminders"
SHEET_REMINDER_SCHEDULES = "ReminderSchedules"
SHEET_TELECONSULT_SESSIONS = "TeleconsultSessions"
SHEET_TELECONSULT_QUEUE = "TeleconsultQueue"

# LINE Messaging API Configuration
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
NURSE_GROUP_ID = os.environ.get("NURSE_GROUP_ID")
LINE_API_URL = "https://api.line.me/v2/bot/message/push"

# Logging Configuration
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)

def get_logger(name):
    """Get logger instance for a module"""
    return logging.getLogger(name)

# Time of Day Mapping
TIME_OF_DAY_MAP = {
    "morning": "09:00",
    "late_morning": "10:30",
    "noon": "12:00",
    "afternoon": "14:00",
    "evening": "18:00",
    "night": "20:00",
    "เช้า": "09:00",
    "สาย": "10:30",
    "เที่ยง": "12:00",
    "บ่าย": "14:00",
    "เย็น": "18:00",
    "กลางคืน": "20:00"
}

# Risk Assessment Configuration
RISK_DISEASES = {"เบาหวาน", "หัวใจ", "ความดัน", "ไต", "มะเร็ง"}

DISEASE_MAPPING = {
    "hypertension": "ความดัน",
    "high blood pressure": "ความดัน",
    "blood pressure": "ความดัน",
    "diabetes": "เบาหวาน",
    "type 1 diabetes": "เบาหวาน",
    "type 2 diabetes": "เบาหวาน",
    "t2d": "เบาหวาน",
    "cancer": "มะเร็ง",
    "tumor": "มะเร็ง",
    "kidney": "ไต",
    "renal": "ไต",
    "heart": "หัวใจ",
    "cardiac": "หัวใจ",
    "ความดัน": "ความดัน",
    "เบาหวาน": "เบาหวาน",
    "มะเร็ง": "มะเร็ง",
    "ไต": "ไต",
    "หัวใจ": "หัวใจ",
    "ht": "ความดัน",
    "dm": "เบาหวาน",
}

DISEASE_NEGATIVES = {
    "none", "no", "no disease", "ไม่มี", "ไม่มีโรค",
    "healthy", "null", "n/a", "ไม่"
}

# Follow-up Reminder Configuration
REMINDER_INTERVALS = {
    'day3': {'days': 3, 'name': 'วันที่ 3 หลังจำหน่าย'},
    'day7': {'days': 7, 'name': 'สัปดาห์ที่ 1'},
    'day14': {'days': 14, 'name': 'สัปดาห์ที่ 2'},
    'day30': {'days': 30, 'name': '1 เดือน'}
}

# Time to check for no-response (hours)
NO_RESPONSE_CHECK_HOURS = 24

# Scheduler Configuration
SCHEDULER_TIMEZONE = 'Asia/Bangkok'
SCHEDULER_JOBSTORE = 'default'

# Teleconsult Configuration
OFFICE_HOURS = {
    'start': '08:00',
    'end': '18:00',
    'weekdays': [0, 1, 2, 3, 4]  # Monday=0 to Friday=4
}

ISSUE_CATEGORIES = {
    'emergency': {
        'name_th': 'ฉุกเฉิน',
        'priority': 1,
        'icon': '🚨',
        'max_wait_minutes': 5
    },
    'medication': {
        'name_th': 'ถามเรื่องยา',
        'priority': 2,
        'icon': '💊',
        'max_wait_minutes': 15
    },
    'wound': {
        'name_th': 'แผลผ่าตัด',
        'priority': 2,
        'icon': '🩹',
        'max_wait_minutes': 15
    },
    'appointment': {
        'name_th': 'นัดหมาย/เอกสาร',
        'priority': 3,
        'icon': '📋',
        'max_wait_minutes': 30
    },
    'other': {
        'name_th': 'อื่นๆ',
        'priority': 3,
        'icon': '❓',
        'max_wait_minutes': 30
    }
}

MAX_QUEUE_SIZE = 20
NURSE_RESPONSE_TIMEOUT_MINUTES = 30
