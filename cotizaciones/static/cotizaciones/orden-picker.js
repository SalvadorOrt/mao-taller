(() => {
 const picker=document.querySelector('.tc-order-picker'); if(!picker)return;
 const input=picker.querySelector('input[type=search]');
 const id=document.getElementById('id_orden');
 const results=document.getElementById('tc-orden-resultados');
 let timer,controller;
 input.addEventListener('input',()=>{
  id.value='';clearTimeout(timer);controller?.abort();results.replaceChildren();
  const term=input.value.trim(); if(term.length<2)return;
  timer=setTimeout(async()=>{
   controller=new AbortController();
   try{
    const response=await fetch(picker.dataset.url+'?q='+encodeURIComponent(term),{signal:controller.signal});
    if(!response.ok)throw new Error('search');
    const data=await response.json();results.replaceChildren();
    for(const row of data.results){
     const button=document.createElement('button');button.type='button';button.textContent=row.label;
     button.addEventListener('click',()=>{id.value=row.id;input.value=row.label;results.replaceChildren();});results.append(button);
    }
    if(!data.results.length){const p=document.createElement('p');p.textContent='Sin órdenes en la sucursal operativa con esa búsqueda.';results.append(p);}
   }catch(error){if(error.name!=='AbortError'){const p=document.createElement('p');p.textContent='No se pudo buscar. Inténtalo otra vez.';results.replaceChildren(p);}}
  },250);
 });
})();
