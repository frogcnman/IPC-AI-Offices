# 通过调用GLM-4V-Falsh接口 ，可实现问答、图片分析等功能；
# -*- coding: utf-8 -*-
import base64, os, time, json
from zhipuai import ZhipuAI
from PIL import Image
from io import BytesIO

# GLM开发平台Key
key = "00c80c80f5192d30d0de94941d1628de.mic0bpFJgOqFEC83"
ai_full_text = """一、监控使用地点
家庭
二、成员信息
成员信息
丈夫、妻子、女儿、母亲、宠物
三、安全监控要点
紧急不安全情况：
明烟明火
成年人躺在地上
儿童接触锐器、药品、电器、火柴火机等点火装置
儿童攀爬到高处
人员不当使用家具
四、健康监控要点
不健康行为：
不良作息习惯
不良生活习惯
吸烟
吸食毒品
五、情绪监控要点
不良情绪表现：
哭
发怒
悲伤
沮丧
疲倦
焦虑
不安
六、隐私保护
隐私行为：
裸体
性相关行为
说明： 对于涉及隐私的行为，请勿进行分析描述，确保家庭成员的隐私权得到尊重和保护。
七、分析要求
实时性： 监控图像需实时分析，及时发现并响应异常情况。
准确性： 确保分析结果的准确性，避免误报和漏报（忽略图像上的日期时间和摄像头水印文字）。
详细性： 对于发现的问题，提供详细的情况描述和可能的原因分析。
建议性： 在发现异常情况时，提供相应的建议或应对措施。
八、输出格式
分析结果以JSON格式输出，包括以下字段：

“有人在家”: “是/否”
“人员是否安全”: “是/否”
“身体是否健康”: “是/否”
“心情是否愉悦”: “是/否”
“总结描述”: “详细的情况描述和原因分析,当前环境的总结”"""
tokens_all = 0


def set_aiconfiginfo(akey, full_text):
    global key
    if key and full_text:
        g_key = akey.get("zhipuapi", {})
        if g_key:
            set_key = g_key.get("key", "")
            if set_key:
                key = set_key
        ai_full_text = full_text


def convert_image_to_base64(image_path):
    # Step 1: Load the image using Pillow
    with Image.open(image_path) as img:
        # Step 2: Resize the image to 800x450
        new_size = (800, 450)
        resized_img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Step 3: Encode the resized image to base64
        buffered = BytesIO()
        resized_img.save(buffered, format=img.format)
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')

    return base64_image


def formt_json(str):
    def extract_json(json_str):
        # 去除字符串首尾的 ```json 和 ```
        json_str = json_str.strip().replace("```json", "").replace("```", "")
        return json_str

    # 示例字符串
    json_with_extra_chars = str

    # 提取纯净的JSON字符串
    clean_json_str = extract_json(json_with_extra_chars)

    # 尝试解析JSON字符串
    try:
        json_data = json.loads(clean_json_str)
        return json_data
    except json.JSONDecodeError as e:
        print("JSON解析错误:", e)
        return None


# 文字信息回复接口
def get_chatinfo(chat_msg):
    client = ZhipuAI(api_key=key)

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": chat_msg
                }
            ]
        }
    ]

    try:
        response = client.chat.completions.create(
            model="GLM-4-Flash",  # 确保模型名称正确
            messages=messages
        )
        msg = response.choices[0].message.content
        # 计算请求和响应的tokens数量
        request_tokens = sum(len(message['content'][0]['text'].split()) for message in messages)
        response_tokens = len(msg.split())
        total_tokens = request_tokens + response_tokens
        tokens_in_k = total_tokens / 1000  # 转换为千tokens
        global tokens_all
        tokens_all += tokens_in_k
        print(f"txt使用了：{tokens_in_k}千tokens")
        return msg
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def get_imginfo(imgpath, text, previous_messages=[], atype=0):
    try:
        if atype == 0:
            type_txt = "image_url"
            model_txt = "GLM-4V-Flash"
        elif atype == 1:
            type_txt = "video_url"
            model_txt = "glm-4v-plus"
        # 构建包含上下文信息的提示词
        full_text = text
        # print(f"full_text:{full_text}")
        # 只有在第一次请求时才发送图片
        if not previous_messages:
            with open(imgpath, 'rb') as img_file:
                img_base = base64.b64encode(img_file.read()).decode('utf-8')

            user_message = {
                "role": "user",
                "content": [
                    {
                        "type": type_txt,
                        type_txt: {
                            "url": img_base
                        }
                    },
                    {
                        "type": "text",
                        "text": full_text
                    }
                ]
            }
        else:
            # 后续请求只发送包含上下文信息的文本
            user_message = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": full_text
                    }
                ]
            }

        client = ZhipuAI(api_key=key)  # 填写您自己的APIKey
        messages = previous_messages + [user_message]
        response = client.chat.completions.create(
            model=model_txt,  # 填写需要调用的模型名称
            messages=messages,
            #response_format = {'type': 'json_object'},
            temperature= 0.2
        )
        total_tokens= int(response.usage.total_tokens)

        msg = response.choices[0].message.content

        new_messages = messages + [{"role": "assistant", "content": msg}]
        return msg,total_tokens, new_messages
    except Exception as e:
        print(f"E: {e}")
        return '-1',0, previous_messages


def get_img_glm(img_path, now_time,atype=0):
    try:
        previous_messages = []
        response1, total_tokens, previous_messages = get_imginfo(img_path, ai_full_text, previous_messages, atype)
        # print('返回：', formt_json(response1))
        f_json = formt_json(response1)
        img_minibase = convert_image_to_base64(img_path)
        f_json["total_tokens"]= total_tokens
        #print(type(f_json))
        return f_json, previous_messages
    except Exception as e:
        print(f"GLM图像识别出错: {e}")
        return None, None


def get_txt_glm(data):
    # date为读取到的今日数据
    try:
        aqlst = []
        jklst = []
        xqlst = []
        # 打印数据
        for js_txt in data:
            # print(f"长度:{len(str(js_txt))},内容：{js_txt}")
            if js_txt.get("人员是否安全", "") == "否":
                # print("安全问题：",js_txt)
                aqlst.append({"安全问题": js_txt.get("总结描述", ""), "时间": js_txt.get("时间", "")})
            elif js_txt.get("身体是否健康", "") == "否":
                # print("健康问题：", js_txt)
                jklst.append({"健康问题": js_txt.get("总结描述", ""), "时间": js_txt.get("时间", "")})
            elif js_txt.get("心情是否愉悦", "") == "否":
                # print("心情问题：", js_txt)
                xqlst.append({"心情问题": js_txt.get("总结描述", ""), "时间": js_txt.get("时间", "")})

        jcont = len(data)
        current_time = time.localtime()
        current_year = current_time.tm_year
        current_month = current_time.tm_mon
        current_day = current_time.tm_mday

        settxt = f"今日{current_year}年{current_month}月{current_day}日，昨日安全记录{jcont}条活动数据，涉及安全{aqlst}条、健康{jklst}条及心情{xqlst}条。综合建议，关爱家庭，守护安全与健康，温馨精炼，20-200字。"
        get_msg = get_chatinfo(settxt)
        # print('今日总结：', get_msg)
        return get_msg
    except Exception as e:
        print(f"GLM文字回复出错: {e}")
        return None

# oldmsg = [{"有人在家":"是","人员是否安全":"是","身体是否健康":"是","心情是否愉悦":"是","总结描述":"客厅整洁有序，没有发现任何安全隐患或不健康行为，家庭成员看起来心情愉悦。","时间":"2025-01-13 16:36:45"},{"有人在家":"是","人员是否安全":"是","身体是否健康":"是","心情是否愉悦":"是","总结描述":"图片显示一位穿着蓝色睡衣的女性站在餐厅区域，客厅内有一只小狗在睡觉，没有观察到任何异常行为或安全隐患，整个环境看起来整洁有序。","时间":"2025-01-13 16:37:19"},{"有人在家":"是","人员是否安全":"是","身体是否健康":"是","心情是否愉悦":"是","总结描述":"图片显示一位女士站在客厅里，旁边有一只正在睡觉的猫。没有看到其他人在家。房间看起来整洁有序，没有明显的安全隐患。","时间":"2025-01-13 16:38:31"}]
# 打开JSON文件并读取数据
# json_file = r"./250120.json"
# with open(json_file, 'r') as file:
# 	data = json.load(file)
# print(len(data))
# print(get_txt_glm(data))

# file_path = r"./data/250117.json"
# with open(file_path, 'r', encoding='utf-8') as file:
#	data = json.load(file)
# get_zjmsg = get_txt_glm(data)
# send_dict = {"总结": get_zjmsg}
# print(send_dict)
#
# img_path = r"./img/cache/proframe_1736420469.jpg"
# datetime = "2025-01-11 10:00:00"
# print(get_img_glm(img_path,datetime,0))
#print(f"ai_full_text：,{type(ai_full_text)},{ai_full_text}")

# 移除所有换行符
# cleaned_string = ai_full_text.replace('\n', '')
#
# print(cleaned_string)
