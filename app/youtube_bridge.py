from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from app.operations_routes import youtube_callback
app=FastAPI(title='YouTube OAuth Callback')
@app.middleware('http')
async def guard(request:Request,next):
 if request.headers.get('host','').split(':')[0]!='localhost':return JSONResponse({'error':'仅允许localhost回调'},403)
 response=await next(request);response.headers['Referrer-Policy']='no-referrer';response.headers['Cache-Control']='no-store';return response
app.add_api_route('/api/auth/youtube/callback',youtube_callback,methods=['GET'])
@app.get('/health')
async def health():return {'ok':True,'service':'youtube-callback'}
