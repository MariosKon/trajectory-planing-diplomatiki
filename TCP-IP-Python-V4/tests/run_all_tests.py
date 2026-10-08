"""
运行所有测试
"""

import os
import sys
import subprocess

# 添加SDK路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def run_test(test_file):
    """运行单个测试文件"""
    print(f"\n{'='*60}")
    print(f"运行测试: {test_file}")
    print('='*60)
    
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__)
        )
        
        print(result.stdout)
        
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"测试运行失败: {e}")
        return False


def main():
    """主函数"""
    print("="*60)
    print("Dobot SDK V4 - 测试套件")
    print("="*60)
    
    test_files = [
        'test_basic.py',
        'test_io.py',
        'test_motion.py',
        'test_robot_control.py',
        'test_plugins.py',
        'test_communication.py'
    ]
    
    passed = 0
    failed = 0
    
    for test_file in test_files:
        file_path = os.path.join(os.path.dirname(__file__), test_file)
        
        if os.path.exists(file_path):
            if run_test(file_path):
                passed += 1
            else:
                failed += 1
        else:
            print(f"\n警告: 测试文件不存在 - {test_file}")
            failed += 1
    
    # 输出总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"总计: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n❌ {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
