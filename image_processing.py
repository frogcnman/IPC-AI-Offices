import os
from PIL import Image
import imagehash
import time

def get_image_hash(image_path):
    """
    计算图片的哈希值
    :param image_path: 图片的路径
    :return: 图片的哈希值
    """
    with Image.open(image_path) as img:
        hash_value = imagehash.average_hash(img)
    return hash_value

def deduplicate_images(image_folder, previous_minute, threshold=5):
    """
    去重图片，保留差异明显的图片，并删除原目录中去重过的图片
    :param image_folder: 原始图片文件夹路径
    :param output_folder: 去重后保存图片的文件夹路径
    :param previous_minute: 前一分钟的时间戳
    :param threshold: 哈希距离阈值，默认5，越小越严格
    """
    # 如果输出文件夹不存在，则创建它
    # if not os.path.exists(output_folder):
    #     os.makedirs(output_folder)

    # 初始化图片哈希列表、原始图片计数、去重后图片计数、删除图片计数
    image_hashes = []
    original_count = 0
    deduplicated_count = 0
    deleted_count = 0

    # 遍历原始图片文件夹中的所有文件
    for image_name in sorted(os.listdir(image_folder)):
        # 如果文件名不是以'frame_'开头或者不是图片文件，则跳过
        if not image_name.startswith('frame_') or not image_name.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue

        # 从文件名中提取时间戳并转换为分钟
        timestamp = int(image_name.split('_')[1].split('.')[0])
        # 如果时间戳不在前一分钟内，则跳过
        if timestamp < previous_minute:
            # 原始图片计数加一
            original_count += 1
            # 获取图片的完整路径
            image_path = os.path.join(image_folder, image_name)
            # 计算图片的哈希值
            image_hash = get_image_hash(image_path)
            # 如果当前图片的哈希值与已有哈希值的差异都大于阈值，则认为是新图片
            if all(image_hash - h > threshold for h in image_hashes):
                # 添加到哈希列表中
                image_hashes.append(image_hash)
                # 保存去重后的图片到输出文件夹
                output_path = os.path.join(image_folder, 'pro'+image_name)
                os.rename(image_path, output_path)
                #Image.open(image_path).save(output_path)
                # 去重后图片计数加一
                deduplicated_count += 1
            else:
                # 否则，删除原图片（这里注释掉了，实际使用时可以取消注释）
                os.remove(image_path)
                # 删除图片计数加一
                deleted_count += 1
            #删除原照片
            #os.remove(image_path)
            #os.rename(image_path, image_path+'_old')

    # 打印统计信息
    print(f"原目录照片数量: {original_count}")
    print(f"去重后新目录照片数量: {deduplicated_count}")
    print(f"删除的照片数量: {deleted_count}")


def run_proc_img():
    try:
        img_f = "/home/hzw/IPC_home/img/cache"
        #out_f = "/home/hzw/IPC_home/img/proc"
        # 每分钟执行一次去重操作
        while True:
            try:
                current_minute = int(time.time())
                previous_minute = current_minute - 10  # 获取前XX秒时间戳
                deduplicate_images(img_f, previous_minute)
            except Exception as e:
                print(f"去重错误: {e}")
            time.sleep(60)  # 等待一分钟
    except Exception as e:
        print(f"图片去重发生错误: {e}")