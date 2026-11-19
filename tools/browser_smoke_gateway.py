"""Test-only AI responses for the synthetic browser suite. Never used by app.main itself."""
import json


def gateway(messages):
    value=messages[-1]['content']
    if isinstance(value,str):
        request=json.loads(value)
        if '최근' in request['request'] and not request['answers']:
            return {'name':'시공사 공문','summary':request['request'],'question':{'text':'어느 기간인가요?','options':['전체 기간','2026년 8월']}}
        return {'name':'시공사 공문','summary':request['request'],'question':None,'officialOnly':True}
    rows=[]
    for part in value:
        if part.get('type')!='text':continue
        try:doc=json.loads(part['text'])
        except (ValueError,TypeError):continue
        if not isinstance(doc,dict) or 'fileId' not in doc:continue
        official='협조 공문.pdf' in doc.get('relative','')
        rows.append({'fileId':doc['fileId'],'decision':'match' if official else 'mismatch',
                     'evidence':{'테스트 응답':'합성 브라우저 검사용 고정 응답. 실제 판독 정확도 검사가 아님.'},
                     'docNumber':'DEMO-01' if official else '', 'title':'협조 요청' if official else '',
                     'sender':'샘플 시공사' if official else '', 'recipient':'발주처' if official else ''})
    return {'results':rows}


def install(app):
    app.gateway=gateway
    original=app.make_plan
    def make_plan(*args,**kwargs):
        plan=original(*args,**kwargs)
        row=next((r for r in plan['rows'] if r.get('destination') and not r.get('done')),None)
        if row:row.update(reviewRequired=True,reviewed=False)
        return plan
    app.make_plan=make_plan
