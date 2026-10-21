(() => {
 const picker=document.querySelector('.tc-product-picker');if(!picker)return;
 const input=picker.querySelector('input'),results=document.getElementById('tc-producto-resultados');
 const product=document.getElementById('id_producto_rel'),code=document.getElementById('id_codigo_producto_rel');
 let timer,controller;
 input.addEventListener('input',()=>{
  product.value='';code.value='';clearTimeout(timer);controller?.abort();results.replaceChildren();
  const term=input.value.trim();if(term.length<2)return;
  timer=setTimeout(async()=>{
   controller=new AbortController();
   try{
    const response=await fetch(picker.dataset.url+'?q='+encodeURIComponent(term),{signal:controller.signal});
    if(!response.ok)throw new Error('search');
    const data=await response.json();results.replaceChildren();
    for(const row of data.results){const button=document.createElement('button');button.type='button';button.textContent=row.label;
     button.addEventListener('click',()=>{product.value=row.product;code.value=row.codigo||'';input.value=row.label;
      document.getElementById('id_descripcion_solicitada').value=row.nombre;
      document.getElementById('id_codigo_referencia').value=row.referencia;results.replaceChildren();});results.append(button);}
    if(!data.results.length){const p=document.createElement('p');p.textContent='Sin coincidencias. Puedes escribir una descripción manual.';results.append(p);}
   }catch(error){if(error.name!=='AbortError'){const p=document.createElement('p');p.textContent='No se pudo consultar el catálogo.';results.replaceChildren(p);}}
  },250);
 });
})();
