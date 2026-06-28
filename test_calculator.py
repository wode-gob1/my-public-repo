#!/usr/bin/env python3
"""
测试计算器功能
"""

from calculator import Calculator


def test_calculator():
    calculator = Calculator()
    
    # 测试用例列表 (表达式, 预期结果)
    test_cases = [
        ("2 + 3", 5.0),
        ("10 - 4", 6.0),
        ("5 * 6", 30.0),
        ("20 / 4", 5.0),
        ("(2 + 3) * 4", 20.0),
        ("10 / (2 + 3)", 2.0),
        ("2 + 3 * 4", 14.0),  # 乘法优先级更高
        ("(10 - 2) / (3 + 1)", 2.0),
        ("-5 + 3", -2.0),
        ("10 / 2", 5.0),
        ("((2 + 3) * (4 - 1)) / 5", 3.0),
        ("1 + 2 + 3 + 4 + 5", 15.0),
        ("10 * 2 / 5", 4.0),
    ]
    
    print("开始测试计算器...")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for expression, expected in test_cases:
        try:
            result = calculator.calculate(expression)
            if abs(result - expected) < 1e-9:
                print(f"✓ 通过: {expression} = {result}")
                passed += 1
            else:
                print(f"✗ 失败: {expression} = {result}, 期望 {expected}")
                failed += 1
        except Exception as e:
            print(f"✗ 错误: {expression} 抛出异常: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    
    # 测试错误情况
    print("\n测试错误处理...")
    print("-" * 50)
    
    error_cases = [
        ("10 / 0", "ZeroDivisionError"),
        ("abc", "ValueError"),
        ("2 + @", "ValueError"),
        ("", "ValueError"),
    ]
    
    for expression, expected_error in error_cases:
        try:
            result = calculator.calculate(expression)
            print(f"✗ 应该报错: '{expression}' 返回了 {result}")
        except ZeroDivisionError:
            if expected_error == "ZeroDivisionError":
                print(f"✓ 正确捕获 ZeroDivisionError: '{expression}'")
            else:
                print(f"? 捕获 ZeroDivisionError: '{expression}' (期望 {expected_error})")
        except ValueError as e:
            if expected_error == "ValueError":
                print(f"✓ 正确捕获 ValueError: '{expression}'")
            else:
                print(f"? 捕获 ValueError: '{expression}' (期望 {expected_error})")
        except Exception as e:
            print(f"? 捕获其他异常 {type(e).__name__}: '{expression}'")
    
    print("-" * 50)
    print("测试完成!")


if __name__ == "__main__":
    test_calculator()
