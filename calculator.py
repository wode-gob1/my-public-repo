#!/usr/bin/env python3
"""
Python 计算器 - 支持加减乘除和括号运算
"""

import ast
import operator


class Calculator:
    """一个简单的计算器类，支持加减乘除和括号"""
    
    def __init__(self):
        # 定义支持的运算符映射
        self.operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
        }
    
    def calculate(self, expression: str) -> float:
        """
        计算表达式的值
        
        Args:
            expression: 数学表达式字符串
            
        Returns:
            计算结果
            
        Raises:
            ValueError: 当表达式无效时
            ZeroDivisionError: 当除以零时
        """
        try:
            # 验证表达式只包含合法字符
            self._validate_expression(expression)
            
            # 解析表达式为 AST
            tree = ast.parse(expression, mode='eval')
            
            # 计算结果
            result = self._eval_node(tree.body)
            
            return result
            
        except SyntaxError as e:
            raise ValueError(f"无效的表达式: {e}")
        except ZeroDivisionError:
            raise ZeroDivisionError("不能除以零")
        except Exception as e:
            raise ValueError(f"计算错误: {e}")
    
    def _validate_expression(self, expression: str) -> None:
        """验证表达式是否只包含合法的字符"""
        # 允许数字、运算符、括号、空格、小数点
        allowed_chars = set('0123456789+-*/(). ')
        for char in expression:
            if char not in allowed_chars:
                raise ValueError(f"表达式包含非法字符: '{char}'")
    
    def _eval_node(self, node) -> float:
        """递归评估 AST 节点"""
        # 处理数字常量
        if isinstance(node, ast.Constant):  # Python 3.8+
            return float(node.value)
        ```
            return float(node.n)
        
        # 处理二元运算
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            
            op_type = type(node.op)
            if op_type in self.operators:
                return self.operators[op_type](left, right)
            else:
                raise ValueError(f"不支持的运算符: {op_type}")
        
        # 处理一元负号
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            elif isinstance(node.op, ast.UAdd):
                return operand
            else:
                raise ValueError(f"不支持的一元运算符: {type(node.op)}")
        
        else:
            raise ValueError(f"不支持的表达式类型: {type(node)}")


def main():
    """主函数 - 提供交互式计算器界面"""
    calculator = Calculator()
    
    print("=" * 50)
    print("       Python 计算器")
    print("=" * 50)
    print("支持: +, -, *, /, ()")
    print("输入 'quit' 或 'q' 退出程序")
    print("=" * 50)
    
    while True:
        try:
            # 获取用户输入
            expression = input("\n请输入表达式: ").strip()
            
            # 检查退出命令
            if expression.lower() in ('quit', 'q', 'exit'):
                print("感谢使用，再见！")
                break
            
            # 跳过空输入
            if not expression:
                continue
            
            # 计算并显示结果
            result = calculator.calculate(expression)
            
            # 格式化输出
            if result == int(result):
                print(f"结果: {int(result)}")
            else:
                print(f"结果: {result:.6f}".rstrip('0').rstrip('.'))
                
        except ZeroDivisionError as e:
            print(f"错误: {e}")
        except ValueError as e:
            print(f"错误: {e}")
        except KeyboardInterrupt:
            print("\n\n感谢使用，再见！")
            break
        except EOFError:
            print("\n\n感谢使用，再见！")
            break


if __name__ == "__main__":
    main()
