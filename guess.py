import random

def guess_number_game():
    secret_number = random.randint(1, 100)
    attempts = 0
    
    print("欢迎来到猜数字游戏！")
    print("我已经想好了一个 1 到 100 之间的数字。")
    
    while True:
        try:
            guess = int(input("请输入你猜的数字: "))
            attempts += 1
            
            if guess < secret_number:
                print("太小了！")
            elif guess > secret_number:
                print("太大了！")
            else:
                print(f"恭喜你，猜对了！答案就是 {secret_number}。")
                print(f"你总共猜了 {attempts} 次。")
                break
        except ValueError:
            print("请输入一个有效的整数！")

if __name__ == "__main__":
    guess_number_game()
TASK_COMPLETE