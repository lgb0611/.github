"""Build user-owned study data. Original quotations and app-authored notes stay separate.
Run only in the build environment, not required to use the app.
"""
from pathlib import Path
import json,re,shutil,collections
import fitz
from docx import Document
ROOT=Path(__file__).resolve().parents[1]
UPLOADS=ROOT.parent
cards=[]
lessons=[]
# Each row: pattern | Korean meaning (app translation) | verbatim source quote |
# app-authored usage note | new English example | Korean recall cue
G={
1:('직접 만든 것의 의미', [36,37], r'''
I was thinking of ~ing|~할까 생각하고 있었어|It was my husband's birthday last weekend, so I was thinking of making him a homemade cake!|of 뒤에 명사 또는 동명사. 의무를 뜻하는 should와 구분하세요.|I was thinking of making a photo album.|사진 앨범을 만들어볼까 생각하고 있었어.
I don't see it that way|나는 그렇게 보지 않아|Some people say it's a waste of time when there are so many amazing bakeries but I don't see it that way.|상대의 관점에 동의하지 않는다는 뜻. 앞의 주장에 이어 쓰세요.|Some people say it's pointless, but I don't see it that way.|어떤 사람들은 의미 없다고 하지만, 나는 그렇게 보지 않아.
There's something special about ~ing|~하는 데에는 뭔가 특별한 게 있어|There's something special about making it yourself.|about을 빠뜨리지 마세요. yourself는 '직접', by yourself는 '혼자서'에 초점을 둘 수 있습니다.|There's something special about writing a letter by hand.|손으로 편지를 쓰는 데에는 뭔가 특별한 게 있어.
Think of it as ~|그걸 ~라고 생각해|Hmm, think of it as a compliment...|think of A as B 구조. 해석하는 관점이나 역할을 제안합니다.|Think of it as a chance to practice.|그걸 연습할 기회라고 생각해.
Turns out, ~|알고 보니 ~더라|Turns out, I used salt instead of sugar.|It turns out (that)의 구어적 생략. It turned out that도 올바른 표현입니다.|Turns out, I sent the message to the wrong person.|알고 보니 엉뚱한 사람에게 메시지를 보냈더라.
After ~ing, ...|~한 다음에 ...|After baking and decorating, I proudly brought the beautiful cake to my husband and sang “Happy Birthday.”|앞 동작을 한 사람과 뒤 문장의 주어를 일치시키세요.|After checking the address, I sent the package.|주소를 확인한 다음에 소포를 보냈어.
as someone took their first bite|누군가 첫입을 먹었을 때|But as he took his first bite, he made a funny face.|take a bite = 한입 먹다. 여기서 as는 두 일이 맞물린 시점입니다.|As she took her first bite, she smiled.|그녀가 첫입을 먹었을 때 미소를 지었어.
What does that mean?|그게 무슨 뜻이야?|Interesting? What does that mean?|that은 상대가 방금 한 말이나 상황을 가리킵니다. What do you mean?도 상황에 따라 가능합니다.|You said it was unusual. What does that mean?|특이하다고 했잖아. 그게 무슨 뜻이야?
someone's expression said otherwise|누군가의 표정은 딴말을 하고 있었어|His expression said otherwise. So, I tried a bite myself.|말한 내용과 표정이 어긋나는 상황. otherwise는 앞의 내용과 다름을 나타냅니다.|He said he was fine, but his expression said otherwise.|괜찮다고 했지만 표정은 그렇지 않았어.
At least it saves us from ~|적어도 ~는 피하게 해주잖아|Oh, well! At least it saves us from all those extra calories!|save someone from + 명사/동명사. 과거의 결과를 말하면 saved를 쓸 수 있습니다.|At least it saved us from waiting outside.|적어도 밖에서 기다리는 일은 피하게 해줬어.
'''),
2:('뜻밖의 만남', [38,39], r'''
You'll never guess what happened to me!|나한테 무슨 일이 있었는지 상상도 못 할 거야|You'll never guess what happened to me today!|놀라운 이야기를 꺼내는 도입. 실제로 추측을 요구할 필요는 없습니다.|You'll never guess what happened to me on the train!|기차에서 나한테 무슨 일이 있었는지 상상도 못 할 거야.
struggle to decide ~|~를 결정하기 어려워하다|I was waiting in line at a café, struggling to decide what to order, when the person behind me noticed and said,|struggle to + 동사. 뒤에는 what to choose처럼 의문사+to 구조를 붙일 수 있습니다.|I was struggling to decide which book to buy.|어느 책을 살지 결정하기 어려웠어.
You can't go wrong with ~|~는 믿고 고를 만해|You can't go wrong with the signature menu — it's what they're famous for. Why don't you give it a try?|추천 대상은 with 뒤에. 원자료의 menu는 문맥상 메뉴 품목을 가리킵니다. 앱 예문은 구체적인 대상을 씁니다.|You can't go wrong with this model.|이 모델은 믿고 고를 만해.
lose track of time|시간 가는 줄 모르다|The conversation flowed so easily that I completely lost track of time.|과거는 lost track of time. 대화뿐 아니라 몰입한 활동에도 적용할 수 있습니다.|We lost track of time while talking about books.|책 얘기를 하다가 시간 가는 줄 몰랐어.
run into someone|누군가와 우연히 마주치다|It's been great chatting with you! I hope we run into each other again!|계획된 만남이 아니라 우연한 만남입니다.|I ran into my old teacher at the station.|역에서 예전 선생님을 우연히 만났어.
wait in line|줄을 서서 기다리다|I was waiting in line at a café, struggling to decide what to order, when the person behind me noticed and said,|줄 '안에서' 기다리므로 in line. wait for는 기다리는 대상을 나타냅니다.|I was waiting in line for tickets.|표를 사려고 줄을 서서 기다리고 있었어.
Why don't you give it a try?|한번 해보는 게 어때?|You can't go wrong with the signature menu — it's what they're famous for. Why don't you give it a try?|give it a try는 시도해 보라는 제안입니다.|Why don't you give painting a try?|그림 그리기를 한번 해보는 게 어때?
That sounds like a good choice|좋은 선택인 것 같네요|That sounds like a good choice — thanks!|상대의 설명을 듣고 선택에 긍정적으로 반응합니다.|That sounds like a good choice for beginners.|초보자에게 좋은 선택인 것 같네요.
It's been great chatting with you|얘기 나눠서 정말 좋았어요|It's been great chatting with you! I hope we run into each other again!|대화를 마무리하며 쓰는 인사. chatting with + 사람.|It's been great chatting with you about travel.|여행 이야기를 나눠서 정말 좋았어요.
Who knew that ~ would lead to ~?|~가 ~로 이어질 줄 누가 알았겠어?|Who knew that picking up coffee would lead to meeting a new friend?|lead to 뒤에는 명사/동명사. 예상하지 못한 결과를 돌아봅니다.|Who knew that volunteering would lead to a new friendship?|봉사가 새 우정으로 이어질 줄 누가 알았겠어?
'''),
3:('계획 밖의 모험', [40,41], r'''
be out for a walk|산책을 나와 있다|My husband and I have always been thrill-seekers, so when we were out for a walk and spotted some scooters, we couldn't resist.|be out for + 활동. 과거의 상황이면 were out for a walk.|We were out for a walk after dinner.|저녁을 먹고 산책을 나와 있었어.
spot ~|~를 눈에 띄어 발견하다|My husband and I have always been thrill-seekers, so when we were out for a walk and spotted some scooters, we couldn't resist.|찾아다닌 결과보다 눈에 띈 발견을 묘사하는 데 쓰세요.|We spotted a small bookstore.|작은 서점이 눈에 띄었어.
How do you feel about ~ing?|~하는 거 어때?|How do you feel about going on a little adventure? my husband asked.|about 뒤에 명사/동명사. 직접 제안이나 의견을 물을 때.|How do you feel about joining the workshop?|그 워크숍에 참가하는 거 어때?
I'm down!|좋아, 나도 할래!|I'm down! Let's go!|제안에 응하는 캐주얼한 반응입니다. 낙담이라는 다른 뜻은 문맥으로 구분합니다.|I'm down! Let's book it.|좋아! 예약하자.
end up ~ing|결국 ~하게 되다|We ended up riding our scooters back in the rain, completely soaked.|end up 뒤는 동명사. 계획과 다른 결과에 자주 쓰지만 반드시 그래야 하는 건 아닙니다.|We ended up staying until closing time.|결국 문 닫을 때까지 머물렀어.
not a care in the world|세상 걱정 하나 없이|At first, it was fantastic — the wind in our hair, not a care in the world.|상태를 묘사하는 덩어리. with not a care in the world로 연결할 수 있습니다.|We sat by the lake with not a care in the world.|우리는 세상 걱정 하나 없이 호숫가에 앉아 있었어.
something didn't feel quite right|뭔가 좀 이상하게 느껴졌어|But after a while, something didn't feel quite right.|quite right를 부정해 어딘가 미심쩍음을 표현합니다.|Something didn't feel quite right about the plan.|그 계획은 뭔가 좀 이상하게 느껴졌어.
be supposed to ~|~하기로 되어 있다, ~일 것으로 예상되다|Pretty sure it was supposed to be sunny all day!|일정·규칙·예상 등 문맥으로 뜻을 구분합니다. was supposed to는 과거의 예상.|The train was supposed to arrive at noon.|기차는 정오에 도착할 예정이었어.
completely soaked|완전히 흠뻑 젖은|We ended up riding our scooters back in the rain, completely soaked.|사람이나 옷이 물에 흠뻑 젖은 상태입니다.|We got home completely soaked.|집에 도착했을 때 완전히 흠뻑 젖어 있었어.
I can't complain|불평할 정도는 아니야|But I can't complain — it really was an adventure!|아쉬움이 있어도 대체로 괜찮다고 말하는 반응입니다.|The room was small, but I can't complain.|방은 작았지만 불평할 정도는 아니야.
'''),
4:('답답함에서 벗어나기', [42], r'''
feel stir-crazy|갇혀 지내서 답답해 미칠 것 같다|My husband and I have been feeling stir-crazy after weeks of being stuck inside because of the cold.|단순히 crazy와 달리 오래 실내에 갇혀 지낸 답답함을 표현합니다.|I felt stir-crazy after staying indoors all weekend.|주말 내내 실내에 있어서 답답해 미칠 것 같았어.
take a week off|일주일 쉬다, 휴가를 내다|So, we decided to take a trip to break free and took a week off for a short winter getaway.|take + 기간 + off. 과거형은 took.|We decided to take a week off.|일주일 휴가를 내기로 했어.
Does next Friday work for us?|다음 주 금요일이 우리 일정에 맞을까?|My husband was booking our tickets online, “Does next Friday work for us?”|날짜/시간 + work for + 사람. 가능 일정을 확인합니다.|Does Tuesday afternoon work for you?|화요일 오후에 시간 괜찮아요?
can't afford to ~|~할 여유가 없다|Yeah! We can't afford to go international, so where should we go? I asked.|afford to + 동사원형. 여기서는 비용을 감당할 여유입니다.|We can't afford to stay for two weeks.|2주나 머물 여유는 없어.
I'm up for anything, as long as ~|~하기만 하면 뭐든 좋아|I'm up for anything, as long as it's not too cold. How about Jeju Island?|as long as 뒤에 조건. not을 빼면 의미가 반대로 바뀔 수 있습니다.|I'm up for anything, as long as it's not too crowded.|너무 붐비지만 않으면 뭐든 좋아.
be stuck inside|안에 갇혀 지내다|My husband and I have been feeling stir-crazy after weeks of being stuck inside because of the cold.|be stuck + 장소. 나가고 싶어도 나갈 수 없는 느낌입니다.|We were stuck inside because of the snow.|눈 때문에 안에 갇혀 있었어.
a short winter getaway|짧은 겨울 여행|So, we decided to take a trip to break free and took a week off for a short winter getaway.|getaway는 일상에서 잠시 벗어나는 짧은 여행을 말합니다.|We planned a short winter getaway.|짧은 겨울 여행을 계획했어.
have a great sale going on|좋은 할인 행사를 하고 있다|They've got a great sale going on right now, he suggested.|have got은 have와 같은 소유/상황 표현. sale going on = 진행 중인 할인.|They've got a great sale going on this week.|이번 주에 좋은 할인 행사를 하고 있어.
just like that|그렇게, 그렇게 순식간에|And just like that, our trip to Jeju was set in motion!|일이 간단하거나 빠르게 진행됐다는 연결 표현입니다.|And just like that, we had a plan.|그렇게 순식간에 계획이 생겼어.
set something in motion|계획이나 일이 진행되기 시작하게 하다|And just like that, our trip to Jeju was set in motion!|원문은 수동태 was set in motion. 실제 출발과 계획이 가동되는 것은 구분하세요.|That phone call set our plan in motion.|그 전화로 우리 계획이 본격적으로 움직이기 시작했어.
'''),
5:('월요일의 작은 낙', [44,45], r'''
back to reality|다시 현실로 돌아옴|It feels like our holiday was just a dream that flew by! But now, it's back to reality.|즐거운 시간 뒤 일상으로 복귀하는 상황에 씁니다.|The holiday is over. It's back to reality.|휴가가 끝났어. 이제 다시 현실이야.
take ages|엄청 오래 걸리다|Getting to work today took ages — I still can't get used to rush hour traffic.|take의 과거형은 took. ages는 여기서 긴 시간을 과장합니다.|Finding a parking space took ages.|주차할 곳 찾는 데 엄청 오래 걸렸어.
I wish I could ~|~할 수 있으면 좋겠다|I wish I could just snap my fingers and teleport there in an instant! Impossible, but hey, I can dream!|지금 실제로 하기 어렵거나 불가능한 바람. could 뒤 동사원형.|I wish I could finish everything in an instant.|모든 걸 순식간에 끝낼 수 있으면 좋겠어.
The one thing I look forward to is ~|내가 기대하는 한 가지는 ~야|The one thing I look forward to on Mondays is stopping by my favorite café on the way to work.|look forward to의 to는 전치사이므로 명사/동명사. 보어에도 ~ing를 쓸 수 있습니다.|The one thing I look forward to is seeing my friends.|내가 기대하는 한 가지는 친구들을 만나는 거야.
stop by ~ on the way to ~|~로 가는 길에 ~에 잠깐 들르다|The one thing I look forward to on Mondays is stopping by my favorite café on the way to work.|stop by는 짧은 방문. on the way home은 to 없이 씁니다.|I stopped by the bookstore on the way to work.|출근길에 서점에 잠깐 들렀어.
which means ~|그러니까 ~라는 뜻이야|It's Monday, which means it's time to go back to work.|앞 사실에 대한 결과나 해석을 덧붙입니다.|It's Friday, which means the weekend is almost here.|금요일이야. 그러니까 주말이 거의 다 왔다는 뜻이지.
get used to ~|~에 익숙해지다|Getting to work today took ages — I still can't get used to rush hour traffic.|to 뒤 명사/동명사. used to + 동사원형(과거 습관)과 다릅니다.|I still can't get used to getting up early.|아직도 일찍 일어나는 데 적응이 안 돼.
for here or to go?|드시고 가세요, 가져가세요?|Sure! Is that for here or to go? the clerk asked.|매장 이용인지 포장인지 묻는 표현. from here가 아닙니다.|Is that for here or to go?|드시고 가세요, 가져가세요?
a sprinkle of ~ on top|위에 ~를 조금 뿌린 것|Hi, I'd like a latte with nonfat milk, extra foam, and a sprinkle of cinnamon on top, please.|a sprinkle of + 재료. 소량을 흩뿌려 올리는 뜻입니다.|I'd like a sprinkle of cinnamon on top.|위에 시나몬을 조금 뿌려주세요.
~ makes everything better|~하면 모든 게 좀 나아져|Sipping my latte on the way to work makes everything better!|동명사구가 주어이면 단수 makes. 개인의 기분을 과장해 표현할 수 있습니다.|Listening to music makes everything better.|음악을 들으면 모든 게 좀 나아져.
'''),
6:('선물 선택의 고민', [47,48], r'''
Have I mentioned that ~?|내가 ~라고 말한 적 있나?|Have I mentioned that I'm horrible at buying gifts?|과거부터 지금까지 말한 적이 있는지 묻는 도입입니다.|Have I mentioned that I love old movies?|내가 옛날 영화를 좋아한다고 말한 적 있나?
be horrible at ~ing|~를 정말 못하다|Have I mentioned that I'm horrible at buying gifts?|at 뒤에 명사/동명사. 강한 자기평가이며 모든 상황에서 bad보다 나은 것은 아닙니다.|I'm horrible at remembering names.|나는 이름 외우는 걸 정말 못해.
get better at ~|~를 더 잘하게 되다|I've always wanted to get better at it,|get better at + 명사/동명사. wanted to get better는 실력 향상을 원했다는 뜻입니다.|I've always wanted to get better at cooking.|나는 늘 요리를 더 잘하고 싶었어.
have a pretty bad track record|지금까지 성과가 꽤 좋지 않다|and while I've improved over the years, I still have a pretty bad track record.|track record는 누적 성과. pretty는 여기서 '꽤'입니다.|I have a pretty bad track record with plants.|나는 식물을 키운 성적이 꽤 좋지 않아.
overthink everything|모든 걸 지나치게 고민하다|I overthink everything.|깊이 생각함 자체가 아니라 필요 이상으로 생각하는 것입니다.|I overthink everything when I make plans.|계획을 세울 때 모든 걸 지나치게 고민해.
have no idea what to get someone|누구에게 뭘 사줘야 할지 전혀 모르다|Last week was Valentine's Day, and I had no idea what to get my husband.|get + 사람 + 물건. what to get her = 그녀에게 무엇을 사줄지.|I had no idea what to get my brother.|남동생에게 뭘 사줘야 할지 전혀 몰랐어.
not be into ~|~에 별로 관심이 없다|He's not into chocolate, and snacks alone wouldn't be enough.|be into + 명사/동명사. 싫어한다기보다 별 관심이 없는 경우도 포함합니다.|She's not into expensive gifts.|그녀는 비싼 선물에는 별 관심이 없어.
put it off until the last minute|마지막 순간까지 미루다|After putting it off until the last minute, I finally had to make a decision.|put off + 명사/동명사. it 같은 대명사는 put과 off 사이에 놓습니다.|I put it off until the last minute again.|또 마지막 순간까지 미뤘어.
And guess what?|근데 있잖아?|And guess what? He loved it!|놀랍거나 반가운 결과를 예고하는 말입니다.|And guess what? She loved the idea!|근데 있잖아? 그녀가 그 아이디어를 정말 좋아했어.
This calls for a celebration!|이건 축하할 일이야!|This calls for a celebration!|call for는 여기서 '~이 필요하다, 마땅하다'입니다.|We finished the project. This calls for a celebration!|프로젝트를 끝냈어. 이건 축하할 일이야!
'''),
7:('집 안의 작은 사고', [49,50], r'''
have been ~ing for the past few days|지난 며칠 동안 계속 ~해 왔다|Water has been dripping from our kitchen faucet for the past few days, and it's driving me crazy!|현재까지 이어진 활동. 이미 끝난 과거 회고라면 시간 기준을 바꾸어 had been도 고려합니다.|I've been working on this for the past few days.|지난 며칠 동안 이 일을 계속 해왔어.
It's driving me crazy!|그것 때문에 짜증 나서 미치겠어|Water has been dripping from our kitchen faucet for the past few days, and it's driving me crazy!|불편한 원인이 나에게 미치는 영향을 강조합니다.|That alarm is driving me crazy!|저 알람 때문에 짜증 나서 미치겠어.
take a look at ~|~를 한번 살펴보다|So, I begged my husband to take a look at it.|at 뒤 살펴볼 대상. 부탁을 강화하려면 begged someone to.|Could you take a look at my screen?|내 화면 좀 살펴봐 줄래?
I'm not quite sure if ~|~인지 잘 모르겠어|I'm not quite sure if I'm doing this right, he said.|확신이 부족함을 나타냅니다. if 뒤는 평서문 어순.|I'm not quite sure if I saved the file.|파일을 저장했는지 잘 모르겠어.
figure out how to ~|어떻게 ~하는지 알아내다|It went on for a good five minutes before we finally figured out how to turn the water off.|방법을 알아내는 표현. how to 다음에는 동사원형.|I finally figured out how to change the setting.|드디어 설정을 바꾸는 방법을 알아냈어.
I can't handle another ~|~를 한 번 더 감당하진 못하겠어|I can't handle another night listening to that! Please, just do something — anything!|another 뒤 단수 명사. 밤, 회의, 지연 등 새로운 대상을 넣어 연습합니다.|I can't handle another delay.|또 지연되는 건 감당하지 못하겠어.
go on for a good five minutes|족히 5분 동안 계속되다|It went on for a good five minutes before we finally figured out how to turn the water off.|go on은 계속되다. a good + 시간은 그 정도 시간이 꽉 찼음을 강조합니다.|The noise went on for a good five minutes.|그 소음은 족히 5분 동안 계속됐어.
spend the next few hours ~ing|그 후 몇 시간을 ~하며 보내다|We then spent the next few hours mopping up the kitchen floor.|spend + 시간 + 동명사. 전치사 for를 끼우지 않습니다.|We spent the next few hours cleaning up.|그 후 몇 시간 동안 청소했어.
won't have ~ until then|그때까지 ~가 없을 거야|and we won't have water until then. But at least the dripping sound is gone!|until then은 앞서 언급한 시점까지를 뜻합니다.|We won't have internet until then.|그때까지 인터넷을 못 쓸 거야.
At least ~ is gone|그래도 적어도 ~는 사라졌어|and we won't have water until then. But at least the dripping sound is gone!|나쁜 상황에서도 나아진 한 점을 짚습니다.|At least the noise is gone.|그래도 적어도 소음은 사라졌어.
'''),
8:('쇼핑과 뜻밖의 문제', [51,52], r'''
find something to wear|입을 만한 것을 찾다|So yesterday, I went to the department store to find something to wear.|something to + 동사 = ~할 만한 것. look for clothes도 문맥에 따라 맞습니다.|I need to find something to wear to the event.|행사에 입을 만한 것을 찾아야 해.
Would you like any help ~ing?|~하는 걸 도와드릴까요?|Would you like any help finding something? a clerk asked me.|help 뒤 동명사로 도움을 받을 활동을 제시합니다.|Would you like any help carrying those bags?|그 가방들을 옮기는 걸 도와드릴까요?
What do you have in mind?|어떤 것을 생각하고 있어?|What kind of dress do you have in mind? she asked again.|have ~ in mind는 머릿속에 생각해 둔 것을 말합니다.|What kind of schedule do you have in mind?|어떤 일정을 생각하고 있어?
Something simple and comfortable, but also elegant|심플하고 편하지만 우아하기도 한 것|Something simple and comfortable, but also elegant, I said.|명사를 되풀이하지 않고 something + 형용사로 답합니다.|Something light and comfortable, but also warm.|가볍고 편하지만 따뜻하기도 한 것.
try it on|그걸 입어보다|But as soon as I got home and tried it on again, one of the straps broke.|try on은 옷 등의 착용감을 시험함. 대명사는 사이에 넣어 try it on.|Can I try it on?|입어봐도 될까요?
be getting married in a few weeks|몇 주 후 결혼할 예정이다|My cousin is getting married in a few weeks!|정해 둔 미래 일정에 현재진행형을 쓰는 원문 예입니다. 미래 표현이 이것 하나만 가능한 건 아닙니다.|My friend is getting married in a few weeks.|친구가 몇 주 후 결혼해.
walk out of the store with ~|~를 가지고 가게를 나서다|In the end, I walked out of the store with a cute little red dress that was actually pretty cheap!|구매한 물건을 들고 나서는 결과를 장면으로 표현합니다.|I walked out of the store with a new jacket.|새 재킷을 가지고 가게를 나왔어.
you get what you pay for|값을 낸 만큼의 품질을 얻는다|I guess you get what you pay for!|이 장면에서는 싼 물건의 낮은 품질을 아쉬워하는 말입니다.|It broke already. I guess you get what you pay for.|벌써 망가졌어. 역시 싼 게 비지떡인가 봐.
be amazing at fixing things like this|이런 것을 고치는 데 아주 능숙하다|Luckily, my mother-in-law is amazing at fixing things like this. Hopefully, she can help me out!|at 뒤 동명사. things like this로 비슷한 종류의 물건들을 가리킵니다.|My friend is amazing at fixing things like this.|친구는 이런 걸 고치는 데 정말 능숙해.
Hopefully, someone can help me out|누군가 도와줄 수 있으면 좋겠다|Luckily, my mother-in-law is amazing at fixing things like this. Hopefully, she can help me out!|help someone out은 곤란이나 필요한 일을 도와주는 느낌. hopefully는 바람을 나타냅니다.|Hopefully, the shop can help me out.|가게에서 나를 도와줄 수 있으면 좋겠어.
'''),
9:('부탁과 말다툼', [53,54], r'''
Here's how it went|어떻게 된 일이냐면 이래|Here's how it went:|사건의 전개를 설명하기 전에 쓰는 도입입니다.|Here's how it went yesterday.|어제 어떻게 된 일이냐면 이래.
If you've got a minute, would you ~?|잠깐 시간 있으면 ~해줄래?|Honey, if you've got a minute, would you take out the trash for me?|부탁할 때 짧은 시간을 전제하는 표현. if you have time도 항상 틀린 표현은 아닙니다.|If you've got a minute, would you check this email?|잠깐 시간 있으면 이 이메일 좀 확인해 줄래?
I'll get right on it|바로 그 일에 착수할게|Sure, no problem. Just give me a second to finish this and I'll get right on it.|get right on it = 지체하지 않고 그 일을 시작하다.|I'll get right on it after this call.|이 전화가 끝나면 바로 할게.
This is taking me longer than I expected|이게 예상보다 오래 걸리고 있어|This is taking me longer than I expected!|take + 사람 + 시간. 비교급 longer 뒤에 than을 붙입니다.|The repair is taking me longer than I expected.|수리가 예상보다 오래 걸리고 있어.
work it out|문제나 갈등을 해결하다|Thankfully, we worked it out and took the trash out together — hand in hand.|여기서는 갈등 해결. 운동하다인 work out과 문맥을 구분하세요.|We talked and worked it out.|대화를 해서 문제를 해결했어.
have an argument about ~|~에 대해 말다툼하다|My husband and I had an argument today about getting chores done.|argument는 의견 충돌. fight도 말다툼을 뜻할 수 있으므로 무조건 오답으로 보지 않습니다.|We had an argument about the schedule.|일정을 두고 말다툼했어.
be unusually tired and cranky|유난히 피곤하고 짜증이 나다|I was unusually tired and cranky, so I started nagging him about it.|cranky는 쉽게 짜증을 내는 상태. unusually가 평소와 다름을 나타냅니다.|I was unusually tired and cranky that day.|그날 유난히 피곤하고 짜증이 났어.
get on someone's case about ~|~를 두고 누군가를 닦달하다|Why do you have to get on my case about it when you can see that I'm busy?|캐주얼하며 불만이 담깁니다. 공손한 부탁과 구분하세요.|Please don't get on my case about it.|그 일로 나를 닦달하지 말아줘.
leave someone feeling upset|누군가를 속상하게 만들다|In the end, we ended up raising our voices at each other, which left both of us feeling upset.|leave + 목적어 + feeling + 감정. left는 leave의 과거형.|The argument left both of us feeling upset.|그 말다툼 때문에 둘 다 속상했어.
get to someone|누군가의 신경에 영향을 주다|We both apologized afterward. I think the lack of sleep got to us.|이 문맥에서는 지치게 하거나 예민하게 만드는 영향입니다.|I think the stress got to me.|스트레스 때문에 예민해진 것 같아.
'''),
10:('새 활동과 적성', [56,57], r'''
It wasn't exactly what I was expecting, though|그런데 내가 기대했던 것과는 좀 달랐어|Today was the first day of our new Pilates class. It wasn't exactly what I was expecting, though.|문장 끝 though는 앞 이야기와 대비되는 말을 덧붙입니다. but도 올바른 연결어입니다.|The class was useful. It wasn't exactly what I was expecting, though.|수업은 유익했어. 그런데 내가 기대했던 것과는 좀 달랐어.
bite off more than one can chew|감당할 수 있는 것보다 큰일을 벌이다|I'm afraid we bit off more than we could chew.|과거는 bit off more than we could chew. 능력/시간에 비해 무리한 일을 맡은 상황입니다.|I think I bit off more than I could chew.|내가 감당하기 어려운 일을 벌인 것 같아.
Neither of us could even ~|우리 둘 다 ~조차 할 수 없었어|Neither of us could even touch our toes!|neither of us는 두 사람 모두에 대한 부정입니다.|Neither of us could even finish the first task.|우리 둘 다 첫 과제조차 끝내지 못했어.
stick it out|어려워도 끝까지 버티다|I don't think we'll be able to stick it out for very long.|중도에 그만두고 싶은 상황에서 계속 버티는 것. it을 사이에 둡니다.|We decided to stick it out until Friday.|금요일까지는 버텨보기로 했어.
not be the right fit for ~|~에 잘 맞지 않다|We both agreed that exercising makes sense, but maybe Pilates isn't the right fit for us.|활동·직업·방법과 사람의 적합성을 말합니다.|This course isn't the right fit for me.|이 강좌는 나에게 잘 맞지 않아.
improve our flexibility and health|유연성과 건강을 개선하다|We picked up Pilates to improve our flexibility and health,|원자료의 picked up은 그대로 보존했습니다. 이 카드는 목적을 표현하는 부분을 연습합니다.|We exercise to improve our flexibility and health.|우리는 유연성과 건강을 개선하려고 운동해.
stay focused|집중을 유지하다|It was hard to stay focused when we kept giggling at each other every time we made a mistake.|stay + 형용사 = 그 상태를 유지하다.|It was hard to stay focused in the noisy room.|시끄러운 방에서 집중하기 어려웠어.
keep ~ing|계속 ~하다|It was hard to stay focused when we kept giggling at each other every time we made a mistake.|keep 뒤에 동명사. 과거는 kept.|We kept checking the time.|우리는 계속 시간을 확인했어.
finish out the month|이번 달 남은 기간을 마저 채우다|We're going to finish out the month and then try something new.|finish out + 기간은 남은 기간을 끝까지 마치는 것입니다.|I'll finish out the month before switching classes.|반을 바꾸기 전에 이번 달은 끝까지 다닐 거야.
We'll see|두고 보자|Maybe ping pong? Or weight training? We'll see!|미래에 어떻게 될지 아직 정하지 않았다는 답입니다.|Maybe I'll join again next year. We'll see.|내년에 다시 참가할지도 몰라. 두고 보자.
''')}
for n,(title,imgs,raw) in G.items():
 lid=f'g{n:02d}'
 lessons.append({'id':lid,'title':f'가브리엘 {n}강 · {title}','family':'gabriel','source':'사용자 제공 강의 캡처','images':[f'sources/gabriel_{n:02d}_{i+1}.png' for i in range(len(imgs))]})
 for i,line in enumerate(raw.strip().splitlines(),1):
  fields=line.split('|');assert len(fields)==6,(n,i,fields)
  phrase,meaning,quote,note,ex,ko=fields
  cards.append({'id':f'{lid}_{i:02d}','lesson_id':lid,'expression':phrase,'meaning_ko':meaning,'source_quote':quote,'source_explanation':'강의 캡처의 원어민 표현 칸에서 발췌. 뜻은 앱에서 옮겼습니다.','note':note,'example_en':ex,'cue_ko':ko,'source_locator':f'가브리엘 잉글리시 {n}강 · 사용자 제공 캡처','source_url':f'sources/gabriel_{n:02d}_1.png','level':'core','origin':'curated','quote_type':'강의 캡처 발췌','tags':[]})
 for i,no in enumerate(imgs): shutil.copy2(UPLOADS/f'image({no}).png',ROOT/f'sources/gabriel_{n:02d}_{i+1}.png')
# Read the user's expression PDF without correcting the original.
name='3. KPOP Demon Hunters 표현 정리(219가지).pdf'
pdf=fitz.open(UPLOADS/name)
lessons.append({'id':'kpop','title':'KPOP Demon Hunters · 원자료 표현집','family':'kpop','source':name,'images':[]})
seen=collections.Counter()
for p,page in enumerate(pdf,1):
 lines = collections.OrderedDict()
 for word in page.get_text('words'):
  lines.setdefault((word[5],word[6]),[]).append(word[4])
 text='\n'.join(' '.join(words) for words in lines.values())
 text=re.sub(r'\s+([.,!?;:])',r'\1',text)
 text=text.split('Copyright')[0].replace('KPOP Demon Hunters 표현 정리','').strip()
 chunks=re.split(r'(?m)^(?=\d+\. )',text)
 for chunk in chunks:
  m=re.match(r'(\d+)\.\s*(.+?)\s*:\s*(.*?)\n(.*)',chunk,re.S)
  if not m: continue
  num,expr,meaning,tail=m.groups();seen[num]+=1
  defs,sep,ex=tail.partition('ex)')
  id=f'kpop_{num}_{seen[num]}'
  cards.append({'id':id,'lesson_id':'kpop','expression':expr.strip(),'meaning_ko':meaning.strip(),'source_quote':re.sub(r'\s+',' ',ex).strip(),'source_explanation':re.sub(r'\s+',' ',defs).strip(),'note':'원자료를 자동 추출한 참고 항목입니다. 대사 속 쓰임과 일반 회화의 쓰임은 다를 수 있으며, 상세 설명은 원자료를 우선 확인하세요.','example_en':'','cue_ko':'','source_locator':f'KPOP 표현집 · PDF {p}쪽 · 원번호 {num}'+(' (중복 번호)' if num=='65' else ''),'source_url':f'sources/kpop_expressions.pdf#page={p}','level':'reference','origin':'source_import','quote_type':'원자료 예문','tags':[]})
shutil.copy2(UPLOADS/name,ROOT/'sources/kpop_expressions.pdf')
shutil.copy2(UPLOADS/'1. KPOP Demon Hunters 전체 대본.pdf',ROOT/'sources/kpop_script.pdf')
# DOCX vocabulary notes, linked to exact original sentence and section.
SPEECHES=[('chaplin_great_dictator_study.docx','Chaplin'),('conan_harvard_class_day_study.docx','Conan'),('jobs_stanford_study.docx','Jobs'),('obama_audacity_hope_study.docx','Obama'),('this_is_water_study.docx','This Is Water'),('vanessa_bryant_eulogy_study.docx','Vanessa Bryant'),('bezos_princeton_2010_study.docx','Bezos'),('brown_power_of_vulnerability_study.docx','Brené Brown'),('malala_un_speech_study.docx','Malala'),('portman_harvard_class_day_study.docx','Portman'),('rowling_fringe_benefits_study.docx','Rowling')]
for si,(fn,label) in enumerate(SPEECHES,1):
 lid=f's{si:02d}';lessons.append({'id':lid,'title':label+' · 연설문 표현','family':'speech','source':fn,'images':[]})
 d=Document(UPLOADS/fn);quote='';translation='';section='';count=0;dedup=set()
 for pi,para in enumerate(d.paragraphs):
  t=para.text.strip()
  if t.startswith('■'): section=t
  elif t.startswith('→'): translation=t[1:].strip()
  elif t.startswith('📖'):
   for part in t[1:].split(' / '):
    clean=part.replace('★','').strip()
    m=re.match(r'([A-Za-z][^:：]{1,100})[:：]\s*(.+)',clean)
    if not m: continue
    expr,meaning=m.groups();expr=expr.strip()
    if expr.lower() in dedup:continue
    dedup.add(expr.lower());count+=1
    cards.append({'id':f'{lid}_{count:03d}','lesson_id':lid,'expression':expr,'meaning_ko':meaning.strip(),'source_quote':quote,'source_explanation':part.strip(),'note':'사용자 제공 연설문 해설의 자동 추출 항목입니다. 원문·기존 해설은 그대로 보존하며, 앱의 추가 설명과는 구분합니다.','example_en':'','cue_ko':'','source_locator':f'{label} · {section} · DOCX 문단 {pi+1}','source_url':f'sources/{fn}','level':'reference','origin':'source_import','quote_type':'연설문 원문','tags':[]})
  elif t and re.match('[A-Za-z"“‘\']',t):quote=t
 shutil.copy2(UPLOADS/fn,ROOT/'sources'/fn)
# Point every Gabriel excerpt at its actual screenshot, not merely the lesson's first one.
second_prefixes = {
 1:['Turns out','Oh, well'], 2:['Who knew'],
 3:['Pretty sure','We ended up','But I can’t complain','But I can\'t complain'],
 5:['To go.','Sipping'],
 6:['After putting','I ended up','And guess','Maybe my streak','This calls'],
 7:['It went on','We then spent','The plumber','and we won'],
 8:['In the end','But as soon','I guess','Luckily'],
 9:["I'm still planning",'This is taking','Why do you have to','In the end','We both apologized','Thankfully'],
 10:["We're going to finish",'Maybe ping pong']
}
for card in cards:
 if card['origin']=='curated':
  number=int(card['lesson_id'][1:])
  if any(card['source_quote'].lower().startswith(prefix.lower()) for prefix in second_prefixes.get(number,[])):
   card['source_url']=f'sources/gabriel_{number:02d}_2.png'
# Machine-readable source manifest. Important: the PDF has duplicate item number 65.
out={'version':'1.0.0','built_at':'2026-09-09','lessons':lessons,'cards':cards,'source_policy':'원자료 인용, 앱 작성 학습 노트, 새 연습 예문을 구분합니다. AI의 교정은 별도 판단이며 원자료 문구를 자동 덮어쓰지 않습니다.','import_notes':['KPOP 표현집 파일명은 219가지이지만 원번호 65가 두 번 등장합니다. 두 항목을 별도 ID로 보존했습니다.','연설문은 📖 해설에서 표현을 자동 추출했습니다. 모든 표현의 해설을 새로 검증한 것은 아닙니다.','가브리엘 100개 카드는 캡처 발췌문과 앱 작성 활용 설명으로 구성했습니다. 강의의 모든 문장과 메모를 재현한 것은 아닙니다.']}
(ROOT/'data/library.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('Gabriel:',sum(c['origin']=='curated' for c in cards),'Kpop:',sum(c['lesson_id']=='kpop' for c in cards),'Speech:',sum(c['lesson_id'].startswith('s') for c in cards),'Total:',len(cards))
