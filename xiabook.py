# -*- coding: utf-8 -*-
from urllib import request
from urllib import parse
from urllib import error
from bs4 import BeautifulSoup#用于解析网页
from tkinter import * #界面库
import tkinter.messagebox
import configparser
import chardet 
import time
import sys
import os
import ssl #避免https网站的认证
ssl._create_default_https_context = ssl._create_unverified_context

returnLists = ["\u00a0\u00a0\u00a0\u00a0", "\u3000"] # "\u000d", 

class LabelHtml:
    def __init__(self, label, name, sub):
        self.label = label
        self.name = name
        self.sub = sub

# 从配置文件中读取多项形式一样的内容
def GetConfigItems(config, section):
    items=config.items(section)
    result = []
    for item in items:
        result.append(item[1])
    return result

# 从配置文件中读取多项形式为Label的内容
def GetConfigLabels(config, section):
    items=config.items(section)
    result = []
    for item in items:
        splits = item[1].split(',')
        if len(splits) == 2:
            result.append(LabelHtml(splits[0],splits[1],""))
        elif len(splits) == 3:
            result.append(LabelHtml(splits[0],splits[1],splits[2]))
    return result

# 通过配置文件读取各项信息
config = configparser.ConfigParser()
config.read("conf.ini")

downUrls = GetConfigItems(config, "DownloadUrls")
testUrls = GetConfigItems(config, "TestUrls")
openAutoTest = config.get("TestUrls", "OpenAutoTest") #是否开启自动测试，默认为False
nextPages = GetConfigItems(config, "NextPages")
indexPages = GetConfigItems(config, "IndexPages")

titleList = GetConfigLabels(config, "TitleLabels")
bodyList = GetConfigLabels(config, "BodyLabels")
nextList = GetConfigLabels(config, "NextLabels")
bookList = GetConfigLabels(config, "BookLabels")

pageNum = config.getint("BookInfo", "PageNum")
if pageNum < 0:
    pageNum = 10000000
bookCharset = config.get("BookInfo", "Charset")

# 找到任一texts中文字所对应的url
def FindUrlByText(soup, url, texts):
    t1 = soup.find_all('a')
    for t2 in t1:
        t3 = t2.get('href')
        for text in texts:
            if t2.get_text().strip() == text:
                return parse.urljoin(url, t3)
    return False #找不到就返回False

# 查找所有labels中的文字内容
def GetTextByLabels(soup, labels):
    texts = ""
    for label in labels:
            t1 = soup.find("div", attrs={label.label:label.name})
            if t1:
                if len(label.sub): #还要再找下一层
                    t2 = t1.find(label.sub)
                    if t2:
                        texts += t2.get_text()
                else:
                    texts += t1.get_text()
    return texts

# 得到书名
def GetBookName(url):
    soup = GetSoup(url)
    # 先找到 index页面
    indexUrl = FindUrlByText(soup, url, indexPages)
    # 再确定书名
    if indexUrl:
        soup = GetSoup(indexUrl)
        bookname = GetTextByLabels(soup, bookList)
        if not len(bookname): # 标签找不到，就换个方式找
            bookname = FindHn(soup, False)
        return bookname

# 找到h1到h6中文字，add表示合并起来，还是找到第一条就ok
def FindHn(soup, add):
    hs = ["h1","h2","h3","h4","h5","h6"]
    text = ""
    for hn in hs:
        t1 = soup.find_all(hn)
        for t2 in t1:
            if not add:
                return t2.get_text()
            else:
                text += t2.get_text()
    return text

#写入标题
def WriteTitle(file, soup):
    file.write("\r\n") #分段
    title = GetTextByLabels(soup, titleList)
    if not len(title): #如果前面找不到，则找 h1/h2/h3
        title = FindHn(soup, True)
    file.write(title)
    file.write("\r\n") #分段
    
# 写入主体内容
def WriteBody(file, soup):
    for body in bodyList:
        t1 = soup.find("div", attrs={body.label:body.name})
        if t1:
            content = t1.get_text()
            if len(content):
                # 删掉 script a 等标签中不需要的内容
                delLabels = ["script", "a", "strong", "li", "span"]
                for delLabel in delLabels:
                    t2 = t1.find_all(delLabel)
                    for t3 in t2:
                        content = content.replace(t3.get_text(),"")
                #处理回车为换行
                content = content.replace("\r\n","\r") # 先都换为\r
                content = content.replace("\r","\r\n") # 再都换为 \r\n，目的是把 \r 处理好
                for returnStr in  returnLists:
                    content = content.replace(returnStr,"\r\n")
                file.write(content)
                file.write("\r\n") #分段

# 查找下一页内容的链接
def FindNextUrl(soup, url):
    # 能找到标签，就用标签
    for nextLabel in nextList:
        t1 = soup.find("a", attrs={nextLabel.label:nextLabel.name})
        if t1:
            return parse.urljoin(url, t1.get('href'));
    # 找不到标签就找文字：<a href="/68/68427/19084765.html">下一章</a>
    return FindUrlByText(soup, url, nextPages)

# 把页面的字符编码搞正确了
def GetCharset(response, html):
    charset = "" # 默认为自动检测charset
    if not len(charset): #如果没有明确指定网页的编码，则自动检测
        infos = response.info()
        # print(infos)
        for key, value in infos.items():
            #找到包括字符编码的部分
            if key == "Content-Type" and "charset" in value and '=' in value: 
                charset = value.split('=')[1].lower() # text/html; charset=utf-8
    #第一种方法找不到，就换个库监测字符集                
    if not len(charset): 
        chardit1 = chardet.detect(html)
        charset = chardit1['encoding'].lower()
        
    if len(charset):
        if "gb" in charset: #只要是gb编码，则自动换为gb18030
            charset = "gb18030"
        return charset
    else: #既没有指定字符集编码，网页中又没有找到，则返回 gb18030
        return "gb18030"

# 输入网页url，得到准备好的soup对象
def GetSoup(url, num=5):
    print("正在解析网页：%s"%(url))
    response = False
    try:
        headers = {'User-Agent': 'User-Agent:Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36'}
        req = request.Request(url, headers=headers)
        response = request.urlopen(req, timeout=10)
        html = response.read()
    except error.URLError as e:
        print("第%d尝试失败，原因是："%(5-num+1))
        print(e)
        if num > 0 : #同一个页面，最多尝试五次
            time.sleep(5-num+1) #休息一下先
            return GetSoup(url, num-1)
        else: #尝试五次仍然超时，则重启程序下载本书的剩余部分
            Restart(sys.argv[0], url, True)
            sys.exit()

    if response and html:
        html = html.decode(GetCharset(response, html))
        soup = BeautifulSoup(html, 'html.parser')
        return soup
    
# 把页面文字内容写入文件；返回下一页的url，没有就返回False
def WritePage(file, url):
    soup = GetSoup(url)
    WriteTitle(file, soup)
    WriteBody(file, soup)
    file.flush()
    return FindNextUrl(soup, url)

#默认书籍放到 C盘的xiabook目录下
bookDir = "c:/xiabook/"
    
def WriteBook(url):
    print("开始下载链接: "+url)
    try:
        urlname = parse.urlsplit(url)[1]
        truename = GetBookName(url) #看能否找到真正的书名
        fileMode = 'w'
        if addMode: #如果是追加模式，则open的参数要改掉
            fileMode = 'a'
        # 创建目录
        if not os.path.exists(bookDir):
            os.makedirs(bookDir)
        file = open(bookDir+"%s-%s.txt"%(truename,urlname), fileMode, encoding=bookCharset) 
        for i in range(0, pageNum): # 下载指定的页数
            if url:
                url = WritePage(file, url)
                time.sleep(1+i*1.0/pageNum) #休息一下
            else: # 找不到了就跳出来
                break
        file.close()
    except BaseException as e:
        print("下载链接%s失败，原因是："%(url))
        print(e)
    print("下载结束！")

def Restart(cmd, url, add=False):
    if add: #是否为追加模式
        url = "-a "+url 
    if ".py" in cmd: #python启动方式
        os.system("start python xiabook.py "+ url)
    else: #cmd启动方式
        os.system("start xiabook.exe "+ url)

addMode = False #是否为重启后的追加写入模式

 
#进入GUI模式
def CreateGUI():
    root = tkinter.Tk()
    root.title("xiabook")
    tkinter.Label(root, text="输入要下载的网络小说的地址：").pack()
    urlGUI = tkinter.Entry(root,width=80)
    urlGUI.insert(0,"https://www.sbkk88.com/huangyi/xunqinji/132366.html")
    urlGUI.pack()

    # 既然是用界面，那么就下载整本书，忽略配置文件中的设置
    global pageNum
    pageNum = 10000000
    
    def WriteBookbyGUI():
        WriteBook(urlGUI.get())
        tkinter.messagebox.showinfo("xiabook","下载完毕！生成的文件在c:/xiabook/目录中")
    tkinter.Button(root,text="下载",command=WriteBookbyGUI,width=50).pack()
    
    # 进入消息循环
    root.mainloop()

if __name__ == '__main__':
    urls = [] 
    #用户通过命令行输入的url，要优先下载
    if len(sys.argv) > 1: 
        if "-a" == sys.argv[1] and len(sys.argv)>2:
            print(sys.argv)
            addMode = True
            urls.extend(sys.argv[2:len(sys.argv)])
        else:
            urls.extend(sys.argv[1:len(sys.argv)])
    # 在配置文件中写了要下载的url，其次下载
    elif len(downUrls): 
        urls.extend(downUrls)
    #判断进入内部测试模式#判断进入内部测试模式
    elif openAutoTest.lower()=="true": 
        urls.extend(testUrls)
        
    if len(urls)==1: #一本书就直接下载
        WriteBook(urls[0])
        os.system("pause")
    elif len(urls)>1: #多个url下载，则同时启动多个程序下载 
        for url in urls:
            Restart(sys.argv[0], url)
    #前面一个url都没有设置，则进入界面操作
    else: 
        CreateGUI()
    
