(() => {
  if (!InterviewAPI.requireAuth('/grading')) return;
  let session, packet;
  const initialSession = new URLSearchParams(window.location.search).get('session');
  if (initialSession) document.querySelector('#load [name=session]').value = initialSession;
  const status = document.getElementById('status');
  const announce = text => { status.textContent = text; };
  const request = (path, body) => InterviewAPI.request('/grading' + path, body ? { method: 'POST', body: JSON.stringify(body) } : {});
  function criterion(key, label, weight, manual, anchors = {}) {
    const field = document.createElement('fieldset');
    field.dataset.key = key; field.dataset.manual = String(manual);
    const legend = document.createElement('legend'); legend.textContent = label + (weight ? ` (${weight}%)` : ''); field.append(legend);
    if (Object.keys(anchors).length) {
      const guide = document.createElement('details'), title = document.createElement('summary');
      title.textContent = 'Scoring anchors'; guide.append(title);
      for (const [rating, anchor] of Object.entries(anchors)) {
        const line = document.createElement('p'); line.textContent = `${rating} / 4: ${anchor}`; guide.append(line);
      }
      field.append(guide);
    }
    for (const [name, caption, type] of [['rating','Rating 0–4','number'],['rationale','Evidence-based rationale','textarea'],['evidence','Evidence IDs, separated by commas','text']]) {
      const labelEl = document.createElement('label'); labelEl.textContent = caption + ' ';
      const input = document.createElement(type === 'textarea' ? 'textarea' : 'input');
      if (type !== 'textarea') input.type = type;
      input.name = name; input.required = true;
      if (name === 'rating') { input.min = '0'; input.max = '4'; input.step = '1'; }
      if (name === 'rationale') { input.minLength = 20; input.maxLength = 4000; }
      labelEl.append(input); field.append(labelEl, document.createElement('br'));
    }
    return field;
  }
  async function refreshHistory() {
    const history = await request(`/sessions/${session}/reviews`);
    document.getElementById('history').textContent = JSON.stringify(history, null, 2);
    const data = await request(`/sessions/${session}/appeals`), area = document.getElementById('appeals'); area.replaceChildren();
    for (const appeal of data.appeals) {
      const section = document.createElement('section'), description = document.createElement('p');
      description.textContent = `${appeal.status}: ${appeal.reason}`; section.append(description);
      if (appeal.status === 'pending') {
        const form = document.createElement('form'), reason = document.createElement('textarea'), choice = document.createElement('select'), button = document.createElement('button');
        reason.required = true; reason.minLength = 20; reason.maxLength = 4000; reason.placeholder = 'Reason for independent appeal decision'; reason.setAttribute('aria-label','Appeal decision reason');
        choice.setAttribute('aria-label','Appeal decision');
        for (const [value,label] of [['upheld','Uphold review'],['re_review_required','Require new review']]) { const option = document.createElement('option'); option.value = value; option.textContent = label; choice.append(option); }
        button.textContent = 'Record decision'; button.type = 'submit'; form.append(choice, reason, button);
        form.addEventListener('submit', async event => { event.preventDefault(); button.disabled = true; try { await request(`/appeals/${appeal.id}/decision`, {disposition:choice.value,reason:reason.value}); await refreshHistory(); announce('Appeal decision recorded.'); } catch (error) { announce(error.message); } finally { button.disabled = false; } }); section.append(form);
      }
      area.append(section);
    }
  }
  document.getElementById('load').addEventListener('submit', async event => {
    event.preventDefault(); session = new FormData(event.target).get('session').trim();
    if (!/^[a-f0-9-]{36}$/i.test(session)) { announce('Enter a valid session ID.'); return; }
    try {
      const data = await request(`/sessions/${session}/evidence`); packet = data.assessment;
      document.getElementById('facts').textContent = JSON.stringify(data,null,2);
      const area = document.getElementById('criteria'); area.replaceChildren();
      for (const [key,value] of Object.entries(packet.dimensions)) if (value.status !== 'not_applicable') area.append(criterion(key,value.label,value.weight,false,packet.dimension_anchors?.[key]));
      for (const gap of data.external_evaluation.payload.manual_requirements) area.append(criterion(gap,gap,null,true));
      document.getElementById('evidence').hidden = false; await refreshHistory(); announce('Evidence loaded. Review all applicable criteria and coverage gaps.');
    } catch (error) { document.getElementById('evidence').hidden = true; announce(error.message); }
  });
  document.getElementById('review').addEventListener('submit', async event => {
    event.preventDefault(); const button = event.target.querySelector('button'); button.disabled = true;
    const body = {packet_digest:packet.packet_digest,dimensions:{},manual_checks:{}};
    for (const field of event.target.querySelectorAll('fieldset')) (field.dataset.manual === 'true' ? body.manual_checks : body.dimensions)[field.dataset.key] = {rating:Number(field.querySelector('[name=rating]').value),rationale:field.querySelector('[name=rationale]').value,evidence_ids:field.querySelector('[name=evidence]').value.split(',').map(x=>x.trim()).filter(Boolean)};
    try { await request(`/sessions/${session}/reviews`,body); await refreshHistory(); announce('Review revision saved. Publication remains subject to calibration.'); } catch (error) { announce(error.message); } finally { button.disabled = false; }
  });
  document.getElementById('feedback').addEventListener('click', async event => { event.target.disabled = true; try { const result = await request(`/sessions/${session}/feedback`,{}); announce(JSON.stringify(result)); } catch (error) { announce(error.message); } finally { event.target.disabled = false; } });
})();
