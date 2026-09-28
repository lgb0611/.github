/* Authored fallback lessons, not AI inference. Runs without a model or network. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.LabAutoLessons=api;})(typeof window!=='undefined'?window:this,function(){
'use strict';
// phrase, contextual meaning, new situation, authored English example, usage note
const catalog=[
 ['such a surprise','정말 뜻밖인 일 / 큰 놀라움','멀리 사는 친구가 예고 없이 와서 정말 놀랐다고 말하기','It was such a surprise to see my friend at the door.','such a + 명사로 놀라움의 정도를 강조합니다.'],
 ['to see how','얼마나 / 어떻게 ~한지 보고·확인하다','오랜만에 본 동네가 얼마나 달라졌는지 보고 놀랐다고 말하기','I was surprised to see how much the neighborhood had changed.','see how 뒤에는 변화의 정도나 방식이 이어집니다.'],
 ['comes out','작품·제품이 출시되다 / 공개되다','좋아하는 작가의 새 책이 다음 달에 나온다고 알리기','Her new book comes out next month.','책·앨범·영화가 공개되는 문맥의 come out입니다.','\\b(?:album|book|movie|film|song|single|product|game|release)\\b'],
 ['come out','작품·제품이 출시되다 / 공개되다','새 게임이 언제 나오는지 물어보기','When does the new game come out?','작품의 공개·출시 문맥입니다.','\\b(?:album|book|movie|film|song|single|product|game|release)\\b'],
 ['I was thinking of','~할까 생각하고 있었다','주말에 자전거를 빌릴까 생각 중이었다고 말하기','I was thinking of renting a bike this weekend.','of 뒤에는 명사나 동명사가 옵니다.'],
 ["I'm thinking of",'~할까 생각 중이다','수업을 하나 들어 볼까 생각 중이라고 말하기',"I'm thinking of taking a cooking class.",'of 뒤에는 명사나 동명사가 옵니다.'],
 ['I was wondering if','~인지 궁금했다 / 조심스럽게 부탁하다','내일 잠깐 통화할 수 있는지 정중하게 묻기','I was wondering if we could talk tomorrow.','부탁이나 질문을 부드럽게 시작할 때 씁니다.'],
 ['I wonder if','~인지 궁금하다','가게가 아직 열려 있는지 궁금하다고 말하기','I wonder if the store is still open.','if 뒤에는 주어와 동사가 있는 절이 이어집니다.'],
 ['looking forward to','~을 기대하고 있다','주말 여행이 기대된다고 말하기',"I'm looking forward to our weekend trip.",'to 뒤에는 명사나 동명사가 옵니다.'],
 ['get used to','~에 익숙해지다','새 일정에 익숙해지는 데 시간이 필요하다고 말하기','I need some time to get used to the new schedule.','과거 습관 used to와 구분합니다.'],
 ['got used to','~에 익숙해졌다','일찍 일어나는 생활에 익숙해졌다고 말하기','I got used to waking up early.','to 뒤의 동작은 동명사로 표현합니다.'],
 ['ended up','결국 ~하게 되었다','계획이 바뀌어 집에서 저녁을 먹었다고 말하기','We ended up having dinner at home.','의도와 달라진 결과에도 자주 씁니다.'],
 ['end up','결국 ~하게 되다','서두르지 않으면 버스를 놓칠 수 있다고 말하기','We might end up missing the bus.','뒤에 동작을 붙일 때 동명사를 씁니다.'],
 ['turns out','알고 보니 ~이다','알고 보니 두 사람이 같은 학교에 다녔다고 말하기','It turns out we went to the same school.','뒤에 that절을 붙일 수 있습니다.'],
 ['turned out','결과적으로 ~이었다 / ~하게 되었다','걱정했던 행사가 잘 끝났다고 말하기','The event turned out better than I expected.','실제 결과가 어땠는지 설명합니다.'],
 ['as long as','~하기만 하면 / ~하는 동안','오늘 돌려주기만 하면 빌려줘도 된다고 말하기','You can borrow it as long as you return it today.','조건인지 기간인지 원문 문맥에서 구분합니다.'],
 ['even if','설령 ~하더라도','비가 오더라도 산책하겠다고 말하기',"I'll go for a walk even if it rains.",'가정한 조건에도 결과가 달라지지 않음을 나타냅니다.'],
 ['as soon as','~하자마자','도착하면 바로 연락하겠다고 말하기',"I'll call you as soon as I arrive.",'미래의 일을 말해도 시간절은 보통 현재형을 씁니다.'],
 ['make sure','반드시 확인하다 / 확실히 ~하다','나가기 전에 문을 잠갔는지 확인해 달라고 말하기','Please make sure the door is locked.','that절이나 to부정사가 이어질 수 있습니다.'],
 ['made sure','반드시 확인했다 / 확실히 ~했다','모두에게 주소를 알려줬는지 확인했다고 말하기','I made sure everyone had the address.','확인해서 어떤 상태를 보장한 일을 말합니다.'],
 ['figure out','알아내다 / 해결 방법을 찾다','이 기계 사용법을 알아보겠다고 말하기',"I'll figure out how to use this machine.",'문제의 답이나 방법을 찾을 때 씁니다.'],
 ['figured out','알아냈다 / 해결 방법을 찾았다','파일 공유 방법을 드디어 알아냈다고 말하기','I finally figured out how to share the file.','과거에 방법을 찾아낸 일을 설명합니다.'],
 ['come up with','생각해 내다 / 제안하다','더 간단한 계획이 필요하다고 말하기','We need to come up with a simpler plan.','계획·아이디어·해결책을 떠올릴 때 씁니다.'],
 ['came up with','생각해 냈다 / 제안했다','친구가 좋은 해결책을 생각해 냈다고 말하기','My friend came up with a good solution.','come의 과거형 came을 사용합니다.'],
 ['run out of','~을 다 쓰다 / ~이 떨어지다','집에 우유가 다 떨어졌다고 말하기',"We've run out of milk.",'뒤에는 부족해진 물건·시간 등이 옵니다.'],
 ['running out of','~이 거의 다 떨어져 가다','시간이 얼마 남지 않았다고 말하기',"We're running out of time.",'아직 조금 남아 있지만 점점 없어지는 상황입니다.'],
 ['had no idea','전혀 몰랐다','가게가 일찍 닫는 줄 몰랐다고 말하기','I had no idea the store closed so early.','뒤에 몰랐던 사실을 절로 붙일 수 있습니다.'],
 ['have no idea','전혀 모르다','열쇠를 어디에 뒀는지 모르겠다고 말하기','I have no idea where I left my keys.','간접의문문은 주어 다음에 동사가 옵니다.'],
 ['depends on','~에 달려 있다','주말 계획은 날씨에 달려 있다고 말하기','Our weekend plan depends on the weather.','on 뒤에 영향을 주는 조건이 옵니다.'],
 ['in case','~할 경우에 대비해서','비가 올 수 있으니 우산을 챙기라고 말하기','Take an umbrella in case it rains.','단순한 조건 if와 대비 목적의 차이를 확인합니다.'],
 ["there's no point in",'~해 봐야 소용없다','이미 끝난 일을 두고 다툴 필요가 없다고 말하기',"There's no point in arguing about it now.",'in 뒤에는 동명사가 옵니다.'],
 ['instead of','~하는 대신에','운전하는 대신 기차를 타자고 제안하기',"Let's take the train instead of driving.",'of 뒤에는 명사나 동명사가 옵니다.'],
 ['no matter what','무슨 일이 있어도 / 무엇이든','어떤 일이 있어도 곁에 있겠다고 말하기',"I'll be there for you no matter what.",'조건과 관계없이 달라지지 않는 뜻을 전달합니다.'],
 ['supposed to','~하기로 되어 있다 / ~해야 한다','우리가 여섯 시에 만나기로 되어 있다고 말하기',"We're supposed to meet at six.",'be supposed to 뒤에 동사 원형을 씁니다.'],
 ['about to','막 ~하려던 참이다','막 집을 나서려던 참이라고 말하기',"I'm about to leave home.",'be about to로 아주 가까운 미래를 말합니다.'],
 ['it takes','~하는 데 시간이 걸리다','역까지 걸어서 십 분 걸린다고 말하기','It takes ten minutes to walk to the station.','it takes + 시간 + to부정사 형태입니다.'],
 ['what if','만약 ~하면 어떨까 / 어떻게 하지','기차를 놓치면 어떻게 할지 물어보기','What if we miss the train?','가능성을 제안하거나 걱정을 꺼낼 때 씁니다.'],
 ['keep in mind','명심하다 / 염두에 두다','배송에 시간이 걸릴 수 있음을 기억해 달라고 말하기','Keep in mind that delivery may take a few days.','기억해야 할 조건이나 사실을 덧붙입니다.'],
 ['at least','적어도 / 그래도 ~만은','늦었지만 적어도 모두 무사하다고 말하기',"We're late, but at least everyone is safe.",'최소 수량인지 위안의 의미인지 문맥을 확인합니다.'],
 ['when it comes to','~에 관해서라면','음식에 관해서는 친구 의견을 믿는다고 말하기','When it comes to food, I trust my friend.','특정 주제를 한정해 말하기 시작합니다.'],
 ['take care of','돌보다 / 처리하다','예약은 내가 맡겠다고 말하기',"I'll take care of the reservation.",'사람을 돌보거나 일을 맡아 처리한다는 뜻입니다.'],
 ['a lot of','많은 ~','준비하는 데 시간이 많이 걸렸다고 말하기','We spent a lot of time preparing for the event.','셀 수 있는 복수명사와 셀 수 없는 명사에 모두 씁니다.'],
 ['the first time','처음 ~한 때 / 처음으로','처음 방문했을 때 길을 잃었다고 말하기','I got lost the first time I visited the city.','첫 경험의 시점을 연결하는 데 쓸 수 있습니다.'],
 ['at the same time','동시에 / 한편으로는','설레면서도 긴장된다고 말하기',"I'm excited and nervous at the same time.",'두 상황이나 감정이 함께 있음을 표현합니다.'],
 ['be able to','~할 수 있다','내일 행사에 갈 수 있을 것 같다고 말하기',"I'll be able to join you tomorrow.",'조동사 뒤에서도 능력·가능성을 표현할 수 있습니다.'],
 ["can't wait to",'빨리 ~하고 싶다 / ~할 것이 몹시 기대된다','새 카페에 빨리 가 보고 싶다고 말하기',"I can't wait to try the new cafe.",'to 뒤에는 동사 원형을 씁니다.'],
 ['get to know','알아 가다 / 친해지다','새 동료들을 알아 가서 즐겁다고 말하기',"It's nice to get to know my new colleagues.",'처음부터 아는 상태보다 알아 가는 과정을 말합니다.'],
 ['more than I expected','예상했던 것보다 더','수리가 생각보다 비쌌다고 말하기','The repair cost more than I expected.','예상과 실제 결과를 비교합니다.'],
 ['to be honest','솔직히 말하면','솔직히 오늘은 집에서 쉬고 싶다고 말하기',"To be honest, I'd rather stay home today.",'자신의 솔직한 생각을 꺼내는 표현입니다.'],
 ['a little bit','조금 / 약간','조금 긴장되지만 기대된다고 말하기',"I'm a little bit nervous, but I'm excited.",'정도를 부드럽게 낮추는 데 씁니다.'],
 ['one of the','~ 중 하나','이 공원이 내가 좋아하는 장소 중 하나라고 말하기','This park is one of the places I like most.','뒤의 명사는 보통 복수형으로 씁니다.'],
 ['happened to','우연히 ~했다','우연히 역에서 친구를 만났다고 말하기','I happened to meet a friend at the station.','happen to + 동사 원형의 우연 의미인지 확인합니다.','\\bhappened to (?:meet|see|find|notice|be|have|know|hear)\\b'],
 ['as much as','~만큼 / ~이기는 하지만','작년만큼 여행하지 못했다고 말하기',"I didn't travel as much as I did last year.",'비교인지 양보인지 문맥에 따라 뜻이 달라집니다.'],
 ['a chance to','~할 기회','주말에 친구와 대화할 기회가 있었다고 말하기','I had a chance to talk with my friend over the weekend.','chance 뒤에서 어떤 기회인지 to부정사로 설명합니다.'],
 ['the way you','네가 ~하는 방식 / 모습','친구가 어려운 내용을 설명하는 방식이 좋다고 말하기','I like the way you explain difficult ideas.','사람이 행동하는 방식이나 모습을 표현합니다.']
];
function escapeRE(s){return s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');}
const key=s=>s.toLowerCase().replace(/[\s.!?,;:]+/g,' ').trim();
function eligible(c){
 // Keep short replies, repeated utterances and unpunctuated tails in source order.
 // Only standalone sound labels / text without English letters are not speaking material.
 return /[a-z]/i.test(c.text)&&!/^\s*(?:\[(?:music|applause|laughter|laughing|cheering|silence)\]|\((?:music|applause|laughter|laughing|cheering|silence)\))\s*[.!?]?\s*$/i.test(c.text);
}
function pool(cues){return cues.filter(eligible);}
function builtin(video,cues){
 const items=pool(cues).map(c=>{
  const row=catalog.find(r=>new RegExp('\\b'+r[0].replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\b','i').test(c.text)&&(!r[5]||new RegExp(r[5],'i').test(c.text)));
  return {cue_id:c.id,source_text:c.text,expression:c.text,
   meaning_ko:'문장 통째로 듣고 다시 말하기',use_case_ko:'들었던 장면을 떠올리고 문장 전체를 영어로 말하세요.',
   note_ko:(c.chunk_kind==='speech'?'구두점이 부족한 자막을 긴 발화 청크로 묶었습니다. 실제 문장 경계를 듣고 확인하세요. ':'자막의 문장 전체를 골랐습니다. ')+(row?'문장 속 “'+row[0]+'”: '+row[1]+' (전체 문장 번역은 아님). ':'')+'문장 뜻과 새 상황은 무료 AI가 준비되면 추가할 수 있습니다.',
   new_task_ko:'문장을 한 번 듣고 글자를 가린 뒤, 같은 내용을 영어 한 문장으로 다시 말하세요.',new_sample_en:c.text};
 });
 return {video_id:video.id,engine:'builtin',items};
}
return {catalog,builtin,pool,key,eligible};
});
