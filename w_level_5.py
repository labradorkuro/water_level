#coding: utf-8
#水位計測システムセンサー側プログラム

import RPi.GPIO as GPIO #GPIOライブラリをインポート
import time
import os,socket
import struct
from time import sleep
import urllib,urllib2
import fcntl
import struct
import datetime
import json
import threading
import serial
import subprocess


#ピン番号の割り当て方式を「コネクタのピン番号」に設定
GPIO.setmode(GPIO.BOARD)

#使用するピン番号を代入
LED_PIN = 32

LEVEL_1_PIN = 11     #水位１
LEVEL_2_PIN = 13    #水位2
LEVEL_3_PIN = 15    #水位3
LEVEL_4_PIN = 16    #水位4
LEVEL_5_PIN = 18    #水位5

GPIO.setwarnings(False)
#11番ピンを出力に設定し、初期出力をローレベルにする
GPIO.setup(LED_PIN,GPIO.OUT,initial=GPIO.LOW)
GPIO.setup(LEVEL_1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(LEVEL_2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(LEVEL_3_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(LEVEL_4_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(LEVEL_5_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

INTERVAL = 10	#送信インターバル初期値 単位 sec
SLEEPTIME = 0.1 #永久ループのスリープ時間 単位 sec
TEST_INT = 1   #(テスト用)インターバルを10:1/10[60s] 20:1/20[30s] 30:1/30[20s] 60:1/60[10s]
READ_SLEEP = 1  #センサー値取得スリーブ時間　単位sec

#グローバル変数
g_macAddr = 0			#MACアドレス保存用
g_counter = 0			#単に起動してからの計測回数print用
g_sendInterval = 60 		#送信インターバル(秒)
g_cmpTime = 0			#時間経過比較用時刻

level_1 = 0  # 水位
level_2 = 0
level_3 = 0
level_4 = 0
level_5 = 0
level_check = 0

url = 'http://153.126.193.185/hifmis/ajaxlib.php'
#url = ''

#
# MACアドレスの取得
#  IN: インターフェース名 ex)"eht0" "wlan0"
#
def getMacAddr(ifname):

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack('256s', ifname[:15]))
    return ''.join(['%02x:' % ord(char) for char in info[18:24]])[:-1]


#
# 現在日時取得
#  OUT: 2016-10-21 18:34:46
#
def getDatetime():

    datet = datetime.datetime.today()     #現在日付・時刻のdatetime型データの変数を取得
    return datet.strftime("%Y-%m-%d %H:%M:%S")

#
# センサー値取得
#
def readSensor():
    global level_1
    global level_2
    global level_3
    global level_4
    global level_5

    level_1 = readSensor_sub(LEVEL_1_PIN)    #水位計測
    level_2 = readSensor_sub(LEVEL_2_PIN)    #水位計測
    level_3 = readSensor_sub(LEVEL_3_PIN)    #水位計測
    level_4 = readSensor_sub(LEVEL_4_PIN)    #水位計測
    level_5 = readSensor_sub(LEVEL_5_PIN)    #水位計測
    level_check = level_1 + (level_2 * 2)+ (level_3 * 4) + (level_4 * 8) + (level_5 * 16)
    return level_check

#
# 入力ポートチェック
#
def readSensor_sub(pin):
    level_val = 0
    if( GPIO.input(pin) == GPIO.HIGH):
        level_val = 1
    return level_val

#
# 水位データの取得(1分間前回と異なる値を取得した場合に変化したとみなす)
# 入力：前回送信値
def checkLevel(pre_send_value,firstboot):
    ret = 0
    cnt = 1
    while True:
        time.sleep(READ_SLEEP)  # 1秒待ち
        # センサー値取得
        val = readSensor()
        print 'readSensor : %d' % val + '(%d)' %cnt
        if firstboot == 1:
            return val
        if val == pre_send_value:
            ret = pre_send_value
            break
        cnt += 1
        if cnt >= 60:
            ret = val
            break
    return ret

#
# 水位計測メイン処理
#
def main():

    global g_macAddr
    global g_sendInterval
    global g_cmpTime
    global level_1
    global level_2
    global level_3
    global level_4
    global level_5

    g_cmpTime = time.time()

    g_macAddr = getMacAddr("wlan0")
    print g_macAddr
    firstboot = 1
    prev_level = -1
    #無限ループ
    while True:
        # 水位計測
        level_check = checkLevel(prev_level,firstboot)
        #10秒毎に温度湿度を計測して送信する
        if prev_level != level_check or g_cmpTime+g_sendInterval < time.time():
            g_cmpTime = time.time()
            print level_check
            prev_level = level_check
            #HTTP送信
            if url != '':
                params = urllib.urlencode({'func':"regRecord", 'mac_address':g_macAddr, 'level1':level_1, 'level2':level_2, 'level3':level_3, 'level4':level_4, 'level5':level_5})
                try:
                    res = urllib2.urlopen(url, params)
                    print getDatetime(),
                    print "SEND DATA:%s" % params
                    g_cmpTime = time.time()
                    print '-----------------Alpha01-02'
                    res_data =res.read()
                    print res_data,     #,で改行されない
                    json_res = json.loads(res_data)
                    print "status=%s" % json_res['status'] + " int=%s" % json_res['int']
                    if json_res['int'] > 0:
                        g_sendInterval = (json_res['int']/1000)/TEST_INT  #msec ⇒ sec
                    if json_res['status'] == 'OK':
                   	    GPIO.output(LED_PIN,GPIO.HIGH)
                    print '\r'
                except urllib2.URLError, e:
                    g_sendInterval = 10          #返り値のintervalが来ないので10秒としておく
                    print e
                    GPIO.output(LED_PIN,GPIO.LOW)
            firstboot = 0

    #GPIOを開放
    print "GPIOを開放"
    GPIO.cleanup()


if __name__ == '__main__':
  main()
