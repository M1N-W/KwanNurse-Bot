# -*- coding: utf-8 -*-
"""
Teleconsult Feature Testing Script
Test all teleconsult functionality
"""
import sys
sys.path.append('/mnt/user-data/outputs/kwannurse-refactored')

from datetime import datetime
from config import LOCAL_TZ, get_logger
from services.teleconsult import (
    is_office_hours,
    get_category_menu,
    parse_category_choice,
    start_teleconsult,
    cancel_consultation,
    get_queue_info_message
)
from database.teleconsult import (
    create_session,
    add_to_queue,
    update_session_status,
    get_queue_status,
    get_user_active_session
)

logger = get_logger(__name__)


def test_office_hours():
    """Test office hours checking"""
    print("\n" + "="*60)
    print("TEST 1: Office Hours Checking")
    print("="*60)
    
    now = datetime.now(tz=LOCAL_TZ)
    is_open = is_office_hours()
    
    print(f"\n1.1 Current time: {now.strftime('%Y-%m-%d %H:%M (%A)')}")
    print(f"1.2 Office hours: {'✅ OPEN' if is_open else '❌ CLOSED'}")
    
    print("\n✅ Office hours test complete\n")


def test_category_menu():
    """Test category menu generation"""
    print("\n" + "="*60)
    print("TEST 2: Category Menu")
    print("="*60)
    
    menu = get_category_menu()
    print("\n2.1 Generated menu:")
    print(menu)
    
    print("\n✅ Category menu test complete\n")


def test_category_parsing():
    """Test category choice parsing"""
    print("\n" + "="*60)
    print("TEST 3: Category Parsing")
    print("="*60)
    
    test_cases = [
        ("1", "emergency"),
        ("2", "medication"),
        ("ฉุกเฉิน", "emergency"),
        ("ถามเรื่องยา", "medication"),
        ("wound", "wound"),
        ("invalid", None)
    ]
    
    for input_text, expected in test_cases:
        result = parse_category_choice(input_text)
        status = "✅" if result == expected else "❌"
        print(f"   {status} Input: '{input_text}' → Result: '{result}' (Expected: '{expected}')")
    
    print("\n✅ Category parsing test complete\n")


def test_database_operations():
    """Test database operations"""
    print("\n" + "="*60)
    print("TEST 4: Database Operations")
    print("="*60)
    
    test_user = "test_user_tc_001"
    
    # Test 1: Create session
    print("\n4.1 Creating session...")
    session = create_session(
        user_id=test_user,
        issue_type="medication",
        priority=2,
        description="Test question about medication"
    )
    
    if session:
        print(f"   ✅ Session created: {session['session_id']}")
    else:
        print("   ❌ Session creation failed")
        return
    
    # Test 2: Add to queue
    print("\n4.2 Adding to queue...")
    queue_info = add_to_queue(
        session_id=session['session_id'],
        user_id=test_user,
        issue_type="medication",
        priority=2
    )
    
    if queue_info:
        print(f"   ✅ Added to queue: Position {queue_info['position']}")
    else:
        print("   ❌ Queue addition failed")
    
    # Test 3: Get queue status
    print("\n4.3 Getting queue status...")
    status = get_queue_status()
    print(f"   Total in queue: {status['total']}")
    print(f"   By priority: {status['by_priority']}")
    
    # Test 4: Update session status
    print("\n4.4 Updating session status...")
    success = update_session_status(session['session_id'], 'in_progress')
    print(f"   {'✅' if success else '❌'} Status updated to in_progress")
    
    # Test 5: Get active session
    print("\n4.5 Getting active session...")
    active = get_user_active_session(test_user)
    if active:
        print(f"   ✅ Found active session: {active.get('Session_ID')}")
    else:
        print("   ❌ No active session found")
    
    print("\n✅ Database tests complete\n")


def test_teleconsult_flow():
    """Test complete teleconsult flow"""
    print("\n" + "="*60)
    print("TEST 5: Complete Teleconsult Flow")
    print("="*60)
    
    test_user = "test_user_tc_flow"
    
    # Test 1: Start consultation (normal)
    print("\n5.1 Starting normal consultation...")
    result = start_teleconsult(
        user_id=test_user,
        issue_type="wound",
        description="แผลบวมเล็กน้อย"
    )
    
    if result['success']:
        print("   ✅ Consultation started")
        print(f"   Message preview: {result['message'][:100]}...")
    else:
        print(f"   ❌ Failed: {result['message']}")
    
    # Test 2: Try starting another (should fail - already has active)
    print("\n5.2 Trying to start another (should fail)...")
    result2 = start_teleconsult(
        user_id=test_user,
        issue_type="medication",
        description="ถามเรื่องยา"
    )
    
    if not result2['success']:
        print("   ✅ Correctly rejected (already has active session)")
    else:
        print("   ❌ Should have been rejected")
    
    # Test 3: Cancel consultation
    print("\n5.3 Cancelling consultation...")
    cancel_result = cancel_consultation(test_user)
    
    if cancel_result['success']:
        print("   ✅ Consultation cancelled")
    else:
        print(f"   ❌ Cancellation failed: {cancel_result['message']}")
    
    print("\n✅ Flow tests complete\n")


def test_queue_management():
    """Test queue management"""
    print("\n" + "="*60)
    print("TEST 6: Queue Management")
    print("="*60)
    
    # Get current queue
    print("\n6.1 Current queue status:")
    message = get_queue_info_message()
    print(message)
    
    print("\n✅ Queue management test complete\n")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print(" " * 25 + "TELECONSULT TEST SUITE")
    print("="*80)
    
    try:
        # Test 1: Office Hours
        test_office_hours()
        
        # Test 2: Category Menu
        test_category_menu()
        
        # Test 3: Category Parsing
        test_category_parsing()
        
        # Test 4: Database Operations
        test_database_operations()
        
        # Test 5: Complete Flow
        test_teleconsult_flow()
        
        # Test 6: Queue Management
        test_queue_management()
        
        # Summary
        print("\n" + "="*80)
        print(" " * 30 + "TEST SUMMARY")
        print("="*80)
        print("\n✅ ALL TELECONSULT TESTS COMPLETED")
        print("\n📊 Next Steps:")
        print("   1. Check Google Sheets for test data")
        print("   2. Create Dialogflow Intent: ContactNurse")
        print("   3. Test in LINE app")
        print("   4. Monitor nurse notifications")
        print("\n" + "="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    run_all_tests()
