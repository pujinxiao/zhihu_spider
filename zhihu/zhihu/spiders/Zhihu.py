# -*- coding: utf-8 -*-
import scrapy,re,json,datetime
from scrapy.http import Request
from scrapy.loader import ItemLoader
from zhihu.items import ZhihuQuestionItem, ZhihuAnswerItem

try:
    import urlparse as parse #在py3中
except:
    from urllib import parse #在py2中

class ZhihuSpider(scrapy.Spider):
    name = "Zhihu"
    allowed_domains = ["www.zhihu.com"]
    start_urls = ['https://www.zhihu.com/']

    headers = {
        "HOST": "www.zhihu.com",
        "Referer": "https://www.zhizhu.com",
        'User-Agent': "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:51.0) Gecko/20100101 Firefox/51.0"
    }
    '''模拟浏览器头部'''

    # question的第一页answer的请求url,这个链接怎么来的？是点击“更多”来的，为了加载更多的answer；｛｝里面是传参用的
    start_answer_url = "https://www.zhihu.com/api/v4/questions/{0}/answers?sort_by=default&include=data%5B%2A%5D.is_normal%2Cis_sticky%2Ccollapsed_by%2Csug" \
                       "gest_edit%2Ccomment_count%2Ccollapsed_counts%2Creviewing_comments_count%2Ccan_comment%2Ccontent%2Ceditable_content%2Cvoteup_count%2Creship" \
                       "ment_settings%2Ccomment_permission%2Cmark_infos%2Ccreated_time%2Cupdated_time%2Crelationship.is_author%2Cvoting%2Cis_thanked%2Cis_nothelp%2Cup" \
                       "voted_followees%3Bdata%5B%2A%5D.author.is_blocking%2Cis_blocked%2Cis_followed%2Cvoteup_count%2Cmessage_thread_token%2Cbadge%5B%3F%28type%3Dbest_ans" \
                       "werer%29%5D.topics&limit={1}&offset={2}"

    def parse(self, response):
        '''
        提取出html页面中的所有url 并跟踪这些url进行一步爬取
        如果提取的url中格式为 /question/xxx 就下载之后直接进入解析函数
        '''
        all_urls=response.xpath('//@href').extract()
        all_urls=[parse.urljoin(response.url,url) for url in all_urls] #列表遍历，补全域名,也会过滤一些没用的链接
        all_urls=filter(lambda x:True if x.startswith("https") else False,all_urls) #留下开头是https的链接
        for url in all_urls:
            match_obj=re.match("(.*zhihu.com/question/(\d+))(/|$).*",url)
            if match_obj:
                # 如果提取到question相关的页面则下载后交由提取函数进行提取
                request_url=match_obj.group(1)
                yield scrapy.Request(request_url, headers=self.headers, callback=self.parse_question)
                #break #打开注释就只提取一条
            else:
                #pass
                # 如果不是question页面则直接进一步跟踪
                yield scrapy.Request(url, headers=self.headers, callback=self.parse)

    def parse_question(self,response):
        # 处理question页面，从页面中提取出具体的question item
        if "QuestionHeader-title" in response.text:
            # 处理新版本
            match_obj = re.match("(.*zhihu.com/question/(\d+))(/|$).*", response.url)
            if match_obj:
                question_id = int(match_obj.group(2))
            item_loader = ItemLoader(item=ZhihuQuestionItem(), response=response)
            item_loader.add_css("title", "h1.QuestionHeader-title::text")
            item_loader.add_css("content", ".QuestionHeader-detail")
            item_loader.add_value("url", response.url)
            item_loader.add_value("zhihu_id", question_id)
            item_loader.add_css("answer_num", ".List-headerText span::text")
            item_loader.add_css("comments_num", ".QuestionHeader-actions button::text")
            item_loader.add_css("watch_user_num", ".NumberBoard-value::text")
            item_loader.add_css("topics", ".QuestionHeader-topics .Popover div::text")
            question_item = item_loader.load_item()
        else:
            # 处理老版本页面的item提取
            match_obj = re.match("(.*zhihu.com/question/(\d+))(/|$).*", response.url)
            if match_obj:
                question_id = int(match_obj.group(2))
            item_loader = ItemLoader(item=ZhihuQuestionItem(), response=response)
            # item_loader.add_css("title", ".zh-question-title h2 a::text")
            item_loader.add_xpath("title",
                                  "//*[@id='zh-question-title']/h2/a/text()|//*[@id='zh-question-title']/h2/span/text()")
            item_loader.add_css("content", "#zh-question-detail")
            item_loader.add_value("url", response.url)
            item_loader.add_value("zhihu_id", question_id)
            item_loader.add_css("answer_num", "#zh-question-answer-num::text")
            item_loader.add_css("comments_num", "#zh-question-meta-wrap a[name='addcomment']::text")
            # item_loader.add_css("watch_user_num", "#zh-question-side-header-wrap::text")
            item_loader.add_xpath("watch_user_num",
                                  "//*[@id='zh-question-side-header-wrap']/text()|//*[@class='zh-question-followers-sidebar']/div/a/strong/text()")
            item_loader.add_css("topics", ".zm-tag-editor-labels a::text")
            question_item = item_loader.load_item()
        yield scrapy.Request(self.start_answer_url.format(question_id, 20, 0), headers=self.headers, callback=self.parse_answer) #主要是question_id的参数传值
        yield question_item

    def parse_answer(self, reponse):
        #处理question的answer，这边比较好，直接由json的入口
        ans_json = json.loads(reponse.text)
        is_end = ans_json["paging"]["is_end"]
        next_url = ans_json["paging"]["next"]

        #提取answer的具体字段
        for answer in ans_json["data"]:
            answer_item = ZhihuAnswerItem()
            answer_item["zhihu_id"] = answer["id"]
            answer_item["url"] = answer["url"]
            answer_item["question_id"] = answer["question"]["id"]
            answer_item["author_id"] = answer["author"]["id"] if "id" in answer["author"] else None
            answer_item["content"] = answer["content"] if "content" in answer else None
            answer_item["parise_num"] = answer["voteup_count"]
            answer_item["comments_num"] = answer["comment_count"]
            answer_item["create_time"] = answer["created_time"]
            answer_item["update_time"] = answer["updated_time"]
            answer_item["crawl_time"] = datetime.datetime.now()
            yield answer_item
        if not is_end:
            yield scrapy.Request(next_url, headers=self.headers, callback=self.parse_answer)

    def start_requests(self):
        '''第一个执行的函数，准备登录'''
        return [Request('https://www.zhihu.com/#signin',headers=self.headers,callback=self.login)]

    def login(self,response):
        '''登录，但是没有输入验证码'''
        response_text=response.text
        match_xsrf=re.match('.*name="_xsrf" value="(.*?)"',response_text,re.S)
        xsrf=''
        if match_xsrf:
            xsrf=match_xsrf.group(1)
        if xsrf:
            post_data = {
                "_xsrf": xsrf,
                "phone_num": "手机号",  #修改成自己的帐号和密码
                "password": "密码",
                "captcha":''
            }
            '''一共是4个参数，就可以实现登陆'''

            #这里先获取验证码的地址，_xsrf和验证码一一对应，在同一个请求中间
            import time
            t=str(int(time.time()*1000))
            captcha_url="https://www.zhihu.com/captcha.gif?r={0}&type=login".format(t)
            yield Request(captcha_url,headers=self.headers,meta={'post_data':post_data},callback=self.lohin_after_captcha) #传递post_data

    def lohin_after_captcha(self,response):
        '''登录人工输入验证码'''
        with open("captcha.jpg","wb") as f:
            f.write(response.body)
            f.close()
        # from PIL import Image
        # try:
        #     im=Image.open('captcha.jpg')
        #     im.show()
        # except:
        #     pass
        captcha=input('请输入验证码：')
        post_data=response.meta.get('post_data',{}) #没有的,则为空字典
        post_url = "https://www.zhihu.com/login/phone_num"
        post_data['captcha']=captcha
        return [scrapy.FormRequest(
            url=post_url,
            formdata=post_data,
            headers=self.headers,
            callback=self.check_login
        )]

    def check_login(self,response):
        '''检查是否登录成功'''
        text_json=json.loads(response.text)
        if "msg" in text_json and text_json["msg"] == "登录成功":
            print(text_json["msg"])
            for url in self.start_urls:
                yield Request(url, dont_filter=True, headers=self.headers)
                '''dont_filter不过滤；默认调用parse（）'''
        else:
            print('登录失败')