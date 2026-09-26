/* African Buffalo host-site bridge: shared wallet and namespaced game routes. */
(function () {
  'use strict';
  window.hallName = 'Slot_AfricanBuffalo';
  window.game_ver = 'v1.0-african-buffalo-host';
  try {
    localStorage.setItem('ym_disable_hotupdate','1');
    localStorage.setItem('userData', JSON.stringify({account:'guest_african_buffalo', password:'offline'}));
    if(!localStorage.getItem('af_demo_user')) localStorage.setItem('af_demo_user','guest_demo');
  } catch(e) {}

  var listeners = {};
  function emit(name,data){(listeners[name]||[]).slice().forEach(function(cb){try{cb(data)}catch(e){console.error(e)}})}
  function json(v){try{return typeof v==='string'?JSON.parse(v):(v||{})}catch(e){return {}}}

  function currentUid(){return localStorage.getItem('af_demo_user')||localStorage.getItem('gag_uid')||'guest_demo'}
  function roomId(){return Math.max(1,Math.min(4,Number(localStorage.getItem('af_demo_room')||1)||1))}
  function demoHeaders(){return {'Content-Type':'application/json','X-Demo-User':currentUid(),'X-Buffalo-Room':String(roomId())}}
  var spinSequence=0;
  var socket = {
    connected:false,
    on:function(name,cb){(listeners[name]||(listeners[name]=[])).push(cb);if((name==='connected'||name==='connect')&&socket.connected)setTimeout(cb,0);return socket},
    emit:function(name,payload){
      if(name==='LoginGame'){
        socket.connected=true;
        var loginBody=json(payload);loginBody.roomId=roomId();
        fetch('/api/african-buffalo/login',{method:'POST',headers:demoHeaders(),body:JSON.stringify(loginBody)})
          .then(function(r){return r.json()}).then(function(d){emit('loginGameResult',d)})
          .catch(function(){emit('loginGameResult',{resultid:1,Obj:{nGamblingWinPool:8888888,score:100000}})});
        return socket;
      }
      if(name==='LoginfreeCount'){
        fetch('/api/african-buffalo/free-count',{headers:demoHeaders()}).then(function(r){return r.json()}).then(function(d){emit('LoginfreeCountResult',d)})
          .catch(function(){emit('LoginfreeCountResult',{ResultCode:1,freeCount:0})});
        return socket;
      }
      if(name==='lottery'){
        var body=json(payload);body.roomId=roomId();body.clientSpinId=currentUid()+'-'+Date.now()+'-'+(++spinSequence);
        fetch('/api/african-buffalo/spin',{method:'POST',headers:demoHeaders(),body:JSON.stringify(body)})
          .then(function(r){return r.json()}).then(function(result){
            if(result&&result.ResultData&&result.ResultData.viewarray){
              var va=result.ResultData.viewarray;
              va.freeAnim=Array.isArray(va.freeAnim)?va.freeAnim.slice(0,5):[];
              while(va.freeAnim.length<5)va.freeAnim.push(0);
              va.freeAnim=va.freeAnim.map(function(v){v=Number(v);return isFinite(v)&&v>=0?v:0});
              if(!Array.isArray(va.nHandCards))va.nHandCards=[];
              while(va.nHandCards.length<20)va.nHandCards.push(1);
              va.nHandCards=va.nHandCards.slice(0,20).map(function(v){v=Number(v);return isFinite(v)&&v>=1&&v<=13?v:1});
            }
            emit('lotteryResult',result||{ResultCode:0});
          })
          .catch(function(e){console.error('[African Buffalo spin]',e);emit('lotteryResult',{ResultCode:0})});
        return socket;
      }
      return socket;
    },
    disconnect:function(){socket.connected=false},
    close:function(){socket.connected=false}
  };
  window.io={connect:function(){setTimeout(function(){socket.connected=true;emit('connected')},0);return socket}};
  window.AfricanBuffalo_LOBBYNET={disconnect:function(){}};
  window.GoldenCentury_LOBBYNET={disconnect:function(){}};
})();
