/** Anonymous page-view funnel; no text, contacts, URL query, or persistent IDs. */
export function createWidgetAnalytics({apiBase,clientId,readPath,paths=['/']}) {
  let view=null,path=null;
  const allowedPaths=new Set(paths.map(value=>value.replace(/\/+$/,'')||'/'));
  const seen=new Set();
  return (kind,ids={})=>{
    try {
      const key=kind==='submit'?`${kind}:${ids.request_id}`:kind;
      if(seen.has(key)||seen.size>=100)return;
      if(!view){
        view=crypto.randomUUID();
        const candidate=String(readPath()).split(/[?#]/,1)[0].replace(/\/+$/,'')||'/';
        path=allowedPaths.has(candidate)?candidate:'(other)';
      }
      seen.add(key);
      const body={client_id:clientId,view_id:view,kind,path};
      if(kind==='submit'){body.sid=ids.sid;body.request_id=ids.request_id;}
      // Analytics never holds up an ask, form render or submission. No retries.
      void fetch(`${apiBase.replace(/\/$/,'')}/api/widget-events?client_id=${encodeURIComponent(clientId)}`,{
        method:'POST',headers:{'Content-Type':'application/json'},credentials:'omit',
        body:JSON.stringify(body),keepalive:true,
      }).catch(()=>{});
    } catch { /* Optional observation cannot break user actions. */ }
  };
}
