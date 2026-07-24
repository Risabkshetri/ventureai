import asyncio
from app.core.supabase_client import supabase_service_client

async def undo_meeting():
    print('Fetching meetings with service role...')
    response = supabase_service_client.table('meeting_requests').select('*, startups(startup_name), users!meeting_requests_investor_id_fkey(name)').execute()
    data = response.data
    
    target_id = None
    for req in data:
        startup_name = req.get('startups', {}).get('startup_name', '').lower() if req.get('startups') else ''
        investor_name = req.get('users', {}).get('name', '').lower() if req.get('users') else ''
        status = req.get('status')
        req_id = req.get('id')
        print(f'Found: Startup: {startup_name}, Investor: {investor_name}, Status: {status}, ID: {req_id}')
        if 'volt' in startup_name and 'shiva' in investor_name:
            target_id = req_id
            break
            
    if target_id:
        print(f'Deleting meeting request {target_id}...')
        delete_resp = supabase_service_client.table('meeting_requests').delete().eq('id', target_id).execute()
        print('Delete successful:', delete_resp.data)
    else:
        print('Could not find the meeting request for Volt Path / Shiva.')

if __name__ == "__main__":
    asyncio.run(undo_meeting())
