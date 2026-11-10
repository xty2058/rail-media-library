"""Extract representative frames and describe them in the hosted service."""
import base64
import json
import math
import os
import subprocess
from urllib.request import Request, build_opener

from search_agent import NoRedirect, settings, within


def run(*args):
    result = subprocess.run(args,capture_output=True,timeout=45,check=False)
    if result.returncode:
        raise ValueError('无法读取媒体文件，请检查文件格式')
    return result.stdout


def describe(poster):
    config = settings()
    data = base64.b64encode(poster.read_bytes()).decode()
    prompt = '仅描述实际可见的画面。给出简短中文描述和最多 8 个标签。不要推测地点或版权。仅返回 JSON，字段 description 和 tags。'
    body = json.dumps({'model':os.environ.get('MEDIA_VISION_MODEL','qwen-vl-plus'),'max_tokens':300,
        'response_format':{'type':'json_object'},'messages':[{'role':'user','content':[
        {'type':'text','text':prompt},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+data}}]}]}).encode()
    request = Request(config['base_url'].rstrip('/')+'/chat/completions',body,headers={
        'Content-Type':'application/json','Authorization':'Bearer '+config['api_key']})

    def fetch():
        with build_opener(NoRedirect()).open(request,timeout=25) as response:
            return json.loads(response.read(65537))

    result = within(25,fetch)
    content = json.loads(result['choices'][0]['message']['content'])
    description, tags = content['description'], content['tags']
    if not isinstance(description,str) or not description.strip() or not isinstance(tags,list):
        raise ValueError('描述模型没有返回可用结果')
    return description.strip()[:300],[tag.strip()[:40] for tag in tags[:8] if isinstance(tag,str) and tag.strip()]


def analyze(source, folder):
    video = source.suffix.lower() in ('.mp4','.mov','.m4v')
    info = json.loads(run('ffprobe','-v','error','-protocol_whitelist','file',
        '-select_streams','v:0','-show_entries','stream=width,height:format=duration',
        '-of','json',str(source)))
    stream = info['streams'][0]
    width,height = int(stream['width']),int(stream['height'])
    duration = float(info['format'].get('duration',0)) if video else 0
    if not math.isfinite(duration) or (video and duration<=0):
        raise ValueError('视频时长无法识别')
    orientation = '横屏' if width>height else '竖屏' if height>width else '方形'
    parts = []
    count = min(6,max(1,math.ceil(duration/25)))
    for index in range(count):
        start,end = duration*index/count,duration*(index+1)/count
        poster = folder/f'{index}.jpg'
        run('ffmpeg','-nostdin','-v','error','-y','-ss',str((start+end)/2),
            '-protocol_whitelist','file','-i',str(source),'-frames:v','1',
            '-vf','scale=768:768:force_original_aspect_ratio=decrease','-q:v','4',str(poster))
        description,tags = describe(poster)
        parts.append(dict(start=start,end=end,poster=poster.name,description=description,
                          tags=list(dict.fromkeys([*tags,orientation])),risks=[]))
    return dict(duration=duration,width=width,height=height,parts=parts)
