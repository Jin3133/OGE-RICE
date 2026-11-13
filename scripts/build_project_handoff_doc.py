from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "禾灌智析项目开发交接文档.docx"


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_border(cell, color="D9D9D9", size="6"):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:color"), color)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def prevent_row_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def set_cell_margins(cell, top=90, start=100, bottom=90, end=100):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_font(run, name="Noto Sans CJK SC", size=11, bold=False, color="000000"):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def add_para(doc, text="", bold_lead=None, keep=False, space_after=5):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.35
    p.paragraph_format.space_after = Pt(space_after)
    if keep:
        p.paragraph_format.keep_with_next = True
    if bold_lead and text.startswith(bold_lead):
        r1 = p.add_run(bold_lead)
        set_font(r1, bold=True)
        r2 = p.add_run(text[len(bold_lead):])
        set_font(r2)
    else:
        r = p.add_run(text)
        set_font(r)
    return p


def add_bullets(doc, items, level=0):
    for item in items:
        p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
        p.paragraph_format.left_indent = Inches(0.25 + level * 0.2)
        p.paragraph_format.first_line_indent = Inches(-0.15)
        p.paragraph_format.line_spacing = 1.25
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(item)
        set_font(r)


def add_numbered(doc, items):
    for index, item in enumerate(items, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.first_line_indent = Inches(-0.15)
        p.paragraph_format.line_spacing = 1.25
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(f"{index}. {item}")
        set_font(r)


def add_table(doc, headers, rows, widths=None, font_size=9.5):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    for i, head in enumerate(headers):
        cell = hdr.cells[i]
        set_cell_shading(cell, "1F4E78")
        set_cell_border(cell)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(head)
        set_font(r, size=9.5, bold=True, color="FFFFFF")
        if widths:
            cell.width = Inches(widths[i])
    for ri, row in enumerate(rows):
        table_row = table.add_row()
        prevent_row_split(table_row)
        cells = table_row.cells
        for ci, value in enumerate(row):
            cell = cells[ci]
            if ri % 2:
                set_cell_shading(cell, "F3F7FA")
            set_cell_border(cell)
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(0)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if ci == 0 else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(str(value))
            set_font(r, size=font_size)
            if widths:
                cell.width = Inches(widths[ci])
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def setup_styles(doc):
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Noto Sans CJK SC"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.line_spacing = 1.35
    normal.paragraph_format.space_after = Pt(5)

    title = styles["Title"]
    title.font.name = "Noto Sans CJK SC"
    title._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    title.font.size = Pt(24)
    title.font.bold = True
    title.font.color.rgb = RGBColor(0, 0, 0)

    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5)):
        style = styles[name]
        style.font.name = "Noto Sans CJK SC"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(12 if name == "Heading 1" else 8)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True

    if "Code Text" not in styles:
        code = styles.add_style("Code Text", WD_STYLE_TYPE.PARAGRAPH)
        code.font.name = "Menlo"
        code._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
        code.font.size = Pt(9)
        code.font.color.rgb = RGBColor(0, 0, 0)
        code.paragraph_format.left_indent = Inches(0.2)
        code.paragraph_format.right_indent = Inches(0.2)
        code.paragraph_format.space_before = Pt(3)
        code.paragraph_format.space_after = Pt(5)


def add_code(doc, text):
    p = doc.add_paragraph(style="Code Text")
    r = p.add_run(text)
    r.font.name = "Menlo"
    r.font.size = Pt(9)


def add_heading(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True
    return p


def build():
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.68)
    section.left_margin = Inches(0.78)
    section.right_margin = Inches(0.78)
    setup_styles(doc)

    # Cover
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(105)
    p.paragraph_format.space_after = Pt(22)
    r = p.add_run("禾灌智析项目开发交接文档")
    set_font(r, size=24, bold=True)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("OGE 赛道一水稻种植监测与分阶段参考灌溉需水评估")
    set_font(r, size=14)
    p.paragraph_format.space_after = Pt(60)
    for line in ("项目仓库  Jin3133 OGE RICE", "交接基准日期  2026 年 11 月 5 日", "当前阶段  数据准备与算法输入质量核查"):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(8)
        r = p.add_run(line)
        set_font(r, size=11)
    doc.add_page_break()

    add_heading(doc, "交接摘要", 1)
    add_para(doc, "本项目已完成比赛方案设计、OGE 平台能力摸底、Git 工程搭建、业务后台最小原型、江夏区边界与网格准备、Sentinel 2 时序影像筛选、平台裁剪与导出链路验证，以及首轮标注数据制作。当前工作已经从方案阶段进入数据和算法开发阶段。")
    add_para(doc, "当前最重要的结论是：OGE 平台可以稳定完成 Sentinel 2 数据读取、小网格裁剪、波段选择、NDVI 计算、地图预览和批处理导出，但武汉一号开发计算权限仍不稳定。平台任务显示完成并不代表导出文件内容有效。首轮下载的 15 组四波段和 NDVI 文件中，2025 年 5 月 1 日、5 月 11 日和 7 月 5 日的文件经本地检查为全零；只有 8 月 16 日和 10 月 5 日的 6 组数据通过内容检查。因此，标注工作尚未正式开始，正在补齐并复核早中期时相。")
    add_para(doc, "团队接手时应继续沿用当前主线：先冻结一套经过像元级检查的三个代表网格和五个关键时相，再开展水稻标签制作和模型比较。不要直接依据平台目录状态或旧清单启动标注或训练。")

    add_heading(doc, "一 项目目标与业务范围", 1)
    add_heading(doc, "1 项目定位", 2)
    add_para(doc, "禾灌智析是面向灌区管理人员的水稻种植监测与分阶段参考灌溉需水评估系统。系统使用遥感影像识别水稻种植范围，按管理单元统计面积，并结合水稻生育阶段和相应阶段灌溉定额计算参考灌溉需水量。Web 端计划展示水稻分布、面积、阶段需水、需水关注等级和核查反馈。")
    add_para(doc, "首期业务计算采用分阶段定额法，计算口径为水稻面积乘以对应生育阶段灌溉定额。同期降水用于解释需水背景和调整关注优先级，不在缺少经过验证的规则时直接作为修正系数乘入结果。参考需水量是计划和研判口径，不等同于实际取水量、供水量或田间实灌水量。")
    add_heading(doc, "2 首期业务闭环", 2)
    add_numbered(doc, [
        "管理人员选择或上传分析范围，并确认种植季、当前生育阶段、作物历和阶段灌溉定额。",
        "OGE 读取影像并执行裁剪、特征计算、水稻识别和分区面积统计。",
        "业务后台按照水稻面积和阶段定额计算分阶段参考灌溉需水量，并划分需水关注等级。",
        "Web 端展示地图、统计指标、重点区域和计算依据。",
        "管理人员复核识别边界或业务参数，提交修正后重新计算，并保留版本记录。",
    ])
    add_heading(doc, "3 暂不纳入首期的内容", 2)
    add_bullets(doc, [
        "实际供需对比：目前没有可靠的灌区取水、供水、蓄水、计量设施服务范围和作物归属数据。",
        "ET0 Kc 水量平衡：首期不与定额法叠加，待具备完整气象变量、作物系数和田间水量平衡参数后单独增加。",
        "节水量或调度成效：没有实施措施和实际计量数据时，不能宣称系统已经产生实际节水效果。",
        "全省或全灌区批量运行：目前只做三个代表网格的算法开发数据包，目的是先跑通识别和标注链路。",
    ])

    add_heading(doc, "二 已确定的技术架构", 1)
    add_table(doc, ["层级", "主要职责", "当前状态"], [
        ["OGE 遥感计算层", "检索平台影像，执行裁剪、波段选择、指数计算、模型或算子推理、空间统计和成果发布", "已完成数据读取、裁剪、NDVI、地图预览和批处理导出验证；水稻模型尚未定型"],
        ["业务服务与数据层", "管理任务、边界、作物历、阶段定额和成果版本，计算参考需水与关注等级，调用 OGE 服务", "FastAPI 最小原型已建立，真实 OGE 服务尚未完成发布和联调"],
        ["Web 交互展示层", "任务创建、参数确认、地图和图表展示、重点区域查询、反馈修正与成果导出", "尚未正式开发，计划复用官方 Vue 3 全栈模板"],
        ["Git 工程与数据注册层", "保存脚本、参数、清单、实验记录、后台和前端源码，记录 OGE 资源标识", "仓库和主要目录已建立，部分清单需要按最新质量检查结果更正"],
    ], widths=[1.25, 3.25, 2.4])
    add_para(doc, "工程采用双层管理方式。OGE 保存平台原生数据、用户上传资源、批处理结果和后续服务；Git 仓库保存源代码、参数模板、数据注册表和实验记录。OGE 的代码脚本界面是平铺列表，无法像普通工程一样组织软件包，因此完整代码结构保留在 Git 中，复制到平台的脚本必须自包含并带有清晰编号。")

    add_heading(doc, "三 OGE 平台已探索功能与结论", 1)
    add_heading(doc, "1 数据中心与数据权限", 2)
    add_table(doc, ["对象", "已验证情况", "结论"], [
        ["Sentinel 2 L2A", "产品编号 S2_MSIL2A；能够检索武汉区域场景并在开发中心调用", "当前主数据源，可用于首版算法和流程开发"],
        ["武汉一号融合影像", "曾使用 LJ3II_L1B_Fusion 和有效场景完成读取及 whu cultivated land 运行；后续复测返回无权限", "目录可见或可预览不等于开发计算有权限，暂不作为首版必要输入"],
        ["武汉一号多光谱", "产品 LJ3II_MSS 可检索；最小读取复测返回数据产品无使用权限", "保留候选清单，等待赛事方权限同步后再验证"],
        ["平台模型", "whu cultivated land 在有效武汉一号融合影像上曾成功输出耕地候选区；semanticricefield 被考虑为水稻伪标签模型", "耕地模型不能直接称为水稻结果；水稻模型仍需做输入兼容和效果验证"],
    ], widths=[1.35, 3.5, 2.05])
    add_heading(doc, "2 已验证的遥感处理能力", 2)
    add_bullets(doc, [
        "getCoverage 可读取有效的 S2 MSIL2A 场景。",
        "Geometry.MultiPolygon 可使用 EPSG 32650 米制坐标构造 5 km 网格。MultiPolygon 坐标必须使用四层列表结构。",
        "Coverage.clip 可完成小网格裁剪；直接裁剪完整江夏区边界耗时过长，不适合作为当前交互流程。",
        "Coverage.selectBands 可选择 B02、B03、B04 和 B08 等波段。",
        "Coverage.normalizedDifference 可使用 B08 与 B04 计算 NDVI。",
        "getMap 可生成交互式地图预览，但预览图层属于会话结果，不能当作持久化数据。",
        "Coverage.export 可生成批处理任务，设置输出坐标系、分辨率和 TIF 格式后存入我的资源下的批处理结果。",
        "上传的 GeoJSON 可通过 myData 路径读取。平台已验证江夏区投影边界 myData/jiangxia_420115_utm50n.geojson。",
    ])
    add_heading(doc, "3 平台行为和限制", 2)
    add_table(doc, ["现象", "影响", "当前处理方式"], [
        ["代码脚本只能平铺保存", "不利于模块化和包管理", "本地仓库保持编号化工程结构，平台脚本保持自包含"],
        ["交互运行常停留在等待服务端推送", "不能只依赖控制台完成提示", "以地图是否出图、任务是否创建和结果文件是否可读取为验收依据"],
        ["完整行政区裁剪耗时过长", "整区在线计算容易阻塞", "使用 5 km 网格异步处理，再汇总或拼接"],
        ["SCL 和 bandNames 调用不稳定", "暂时无法建立稳定的质量波段流程", "先用目录云量、有效像元检查、目视复核和多时相信息控制质量"],
        ["批处理队列可能提示队列已满", "导出任务无法提交", "刷新不能保证解决；等待队列释放或先使用公开同源数据完成本地质量核查"],
        ["平台自动追加扩展名", "手动输入 tif 后可能生成 tif tif", "任务文件名不再手动填写扩展名"],
        ["任务完成不代表像元有效", "可能得到尺寸正常但全零的文件", "下载后必须检查像元范围、有效比例、亮度和目视效果"],
    ], widths=[1.65, 2.25, 3.0])

    add_heading(doc, "四 示范区和数据准备工作", 1)
    add_heading(doc, "1 示范区选择变化", 2)
    add_para(doc, "项目最初研究过黄陂区，以武汉一号高分辨率影像覆盖不同地貌类型。随后发现当前固定 Sentinel 2 瓦片 T50RKU 主要覆盖武汉南部江夏方向，不覆盖黄陂中部；同时武汉一号开发计算权限不稳定。为了先建立可运行的数据和算法链路，当前示范区调整为武汉市江夏区。黄陂区武汉一号候选清单仍保留，但属于延期候选，不是当前主线。")
    add_heading(doc, "2 江夏区空间数据", 2)
    add_table(doc, ["项目", "内容"], [
        ["行政区代码", "420115"],
        ["WGS 84 范围", "114.036723 至 114.598676 E，29.969132 至 30.533369 N"],
        ["处理坐标系", "EPSG 32650"],
        ["边界文件", "data/boundaries/jiangxia_420115_wgs84.geojson 和 jiangxia_420115_utm50n.geojson"],
        ["网格体系", "107 个与江夏区相交的 5 km 网格，其中核心网格 83 个、边缘网格 24 个"],
        ["默认任务表", "107 个网格乘以 5 个默认时相，共 535 条任务"],
        ["边界适用范围", "公开行政边界，可用于竞赛原型和区级裁剪；不代表实际灌区供水服务范围"],
    ], widths=[1.65, 5.25])
    add_heading(doc, "3 代表网格", 2)
    add_table(doc, ["网格", "坐标范围 EPSG 32650", "预定用途"], [
        ["JX5K R03C06", "235000 3325000 240000 3330000", "江夏南部样区，训练与规则调试"],
        ["JX5K R07C05", "230000 3345000 235000 3350000", "中西部样区，补充训练和难例修正；已完成单网格链路验证"],
        ["JX5K R10C10", "255000 3360000 260000 3365000", "东北部城郊破碎地物样区，优先保留为独立验证区"],
    ], widths=[1.4, 2.7, 2.8])
    add_para(doc, "三个网格用于先开发算法，不代表已经覆盖江夏区全部农业景观。后续若确认模型需要覆盖丘陵、滨湖、城乡交错等差异，应结合行政区和地形资料补充或替换代表网格。")

    add_heading(doc, "五 遥感数据与当前质量状态", 1)
    add_heading(doc, "1 原定五时相数据包", 2)
    add_para(doc, "平台曾按三个网格和五个日期导出 15 张 NDVI 及 15 张四波段 GeoTIFF。四波段顺序为 B02、B03、B04、B08，输出参数为 EPSG 32650、10 米分辨率和 TIF。原日期为 2025 年 5 月 1 日、5 月 11 日、7 月 5 日、8 月 16 日和 10 月 5 日。")
    add_heading(doc, "2 最新本地内容检查", 2)
    add_table(doc, ["日期", "三个网格的 MS4 与 NDVI", "当前处理决定"], [
        ["2025 05 01", "全部为全零数据", "禁止标注和训练，待替换"],
        ["2025 05 11", "全部为全零数据", "禁止标注和训练，待替换"],
        ["2025 07 05", "原 OGE 导出全部为全零数据", "禁止使用原文件；正在用同源公开影像复核"],
        ["2025 08 16", "三个网格均有有效像元，标注 PNG 可正常显示", "保留"],
        ["2025 10 05", "三个网格均有有效像元，标注 PNG 可正常显示", "保留"],
        ["2025 04 18", "已从公开 Sentinel 2 L2A 同源真彩色影像裁出三个 500 × 500 网格", "作为早期替代候选，尚需总览复核后纳入最终清单"],
        ["2025 06 05", "整景真彩色影像已下载，但 R03C06 裁剪结果为全零", "不能直接纳入，需换日期或检查相邻瓦片"],
    ], widths=[1.25, 3.55, 2.1])
    add_para(doc, "旧的 data/catalog/jiangxia_algorithm_dataset.csv 和 jiangxia_multispectral_dataset.csv 仍将这些平台任务记录为 export completed。该字段只表示批处理任务完成，不表示数据通过像元内容检查。团队在最终冻结数据前必须更新清单状态，建议增加 content qc status、valid fraction 和 rejection reason 字段。")
    add_heading(doc, "3 当前标注目录", 2)
    add_code(doc, "data/raw/labeling/source_geotiff/\n  JX5K_R03C06/  JX5K_R07C05/  JX5K_R10C10/\n    ms4/    OGE 导出的四波段 GeoTIFF\n    ndvi/   OGE 导出的 NDVI GeoTIFF\n    tci/    补充的真彩色 GeoTIFF\n  _scene_cache/  公开 Sentinel 2 L2A 整景真彩色缓存\n\ndata/raw/labeling/tolabel/\n  images_rgb/             当前通过检查的 Labelme 主图\n  reference_false_color/  假彩色辅助判读图\n  reference_ndvi/         NDVI 辅助判读图\n  _invalid_zero_source/   已隔离的全零预览图\n  labelme_manifest.csv    图像与源文件及裁剪偏移关系")
    add_para(doc, "tolabel 目录当前只有 8 月和 10 月的 6 张 RGB 主图正式通过检查。全零预览已移动到 _invalid_zero_source，保留用于追溯但不得标注。4 月真彩色裁剪已生成源 GeoTIFF，尚未写入最终 Labelme 目录。")

    add_heading(doc, "六 标签与模型开发方案", 1)
    add_heading(doc, "1 标签设计", 2)
    add_bullets(doc, [
        "首版采用二值语义分割：水稻为 1，非水稻为 0，无法判读或忽略区域为 255。",
        "伪标签可以由平台水稻模型或规则生成，但不得直接作为真实标签。",
        "人工修正需结合多时相 RGB、假彩色、NDVI 和高分辨率底图。",
        "非水稻样本要主动覆盖水体、建设用地、林地、裸地、旱地和其他高植被地物。",
        "训练集与验证集按完整地块或空间区域隔离，不能随机拆分相邻像元。",
        "JX5K R10C10 在模型定型前优先保留为独立验证区。",
    ])
    add_heading(doc, "2 标注工具", 2)
    add_para(doc, "PlanetMark 因缺少账号未采用。团队已有 Labelme，可直接使用 PNG 主图标注。GeoTIFF 是否能在具体 Labelme 安装中直接打开取决于图像插件和格式支持，因此当前准备 PNG 作为主标注图，同时保留 GeoTIFF 和 manifest，以便后续恢复坐标。")
    add_heading(doc, "3 模型选择现状", 2)
    add_table(doc, ["候选", "作用", "当前判断"], [
        ["semanticricefield", "水稻伪标签或基线", "业务上有吸引力，但需验证平台输入和输出；公开仓库权重不完整，不能直接作为本地部署成品"],
        ["whu cultivated land", "耕地候选区", "曾在有效武汉一号融合影像上跑通；只能输出耕地候选区，不能当作水稻识别结果"],
        ["团队已有语义分割模型", "后续对照或主模型", "尚未验证能否直接在 OGE 环境运行；初赛阶段可先不承诺具体接入方式"],
        ["TerraSegNet 或 Plot Rice", "第二阶段候选", "有参考价值，但训练域与本项目数据不同，需样本和输入适配"],
    ], widths=[1.45, 1.55, 3.9])
    add_para(doc, "比赛更重视业务场景、平台深度应用和完整闭环，因此模型精度不是唯一目标。但算法输出必须经独立样本评价，至少报告水稻类别的精确率、召回率和 F1。当前正确顺序是先冻结数据和标签，再比较平台模型、规则基线和团队模型。")

    add_heading(doc, "七 业务后台与工程代码", 1)
    add_heading(doc, "1 Git 仓库", 2)
    add_table(doc, ["项目", "内容"], [
        ["远程仓库", "https://github.com/Jin3133/OGE-RICE"],
        ["本地路径", "/Users/j/Documents/科研/oge/oge-rice"],
        ["主分支", "main"],
        ["Git 用户", "Jin3133"],
        ["最新已推送提交", "d596d4c record Sentinel NDVI comparison trial"],
        ["当前工作区", "存在较多尚未提交的边界、清单、脚本、文档和本地数据准备变更；提交前应分组检查，避免把大体积原始影像加入 Git"],
    ], widths=[1.65, 5.25])
    add_heading(doc, "2 后台原型", 2)
    add_para(doc, "FastAPI 后台已建立最小可运行结构。现有接口包括健康检查、分阶段参考需水计算，以及调用已发布 OGE 耕地服务的适配接口。业务规则已实现面积乘阶段定额和高、中、低关注等级划分。")
    add_table(doc, ["接口或模块", "功能", "状态"], [
        ["GET /api/health", "返回后台健康状态", "已实现"],
        ["POST /api/v1/stage-demand", "计算阶段参考需水量和关注等级", "已实现并有单元测试"],
        ["POST /api/v1/oge/cultivated-land", "透传登录凭证并调用 OGE 已发布个人算法服务", "代码已实现，尚缺真实服务名、AppKey 和端到端联调"],
        ["backend/app/domain.py", "StageDemand 和 attention_level 业务规则", "已实现"],
    ], widths=[2.15, 3.25, 1.75])
    add_para(doc, "仓库的测试代码使用 unittest 和 FastAPI TestClient。当前虚拟环境未安装 pytest 命令，因此本次检查没有直接执行 pytest。接手者可安装 pytest，或使用 python -m unittest discover 运行现有测试。")
    add_heading(doc, "3 前端状态", 2)
    add_para(doc, "前端尚未正式搭建。计划复用官方 rs fullstack spectral source 中的 Vue 3、Vite、鉴权、相对路径打包和 Docker 托管结构，替换示例的光谱曲线页面，建设任务创建、地图展示、参数确认、重点区域、核查反馈和成果导出页面。前端应在 OGE 识别服务和数据格式基本稳定后进入主开发。")

    add_heading(doc, "八 主要代码和文件索引", 1)
    add_table(doc, ["路径", "用途"], [
        ["README.md", "项目定位、结构和本地后台启动说明"],
        ["oge_scripts/00 至 18", "OGE 数据权限、场景读取、NDVI、裁剪、导出和候选场景检查脚本"],
        ["oge_scripts/90_hgz_wuhan1_permission_test.py", "武汉一号最小权限复测"],
        ["scripts/build_jiangxia_grid_catalog.py", "生成江夏区 5 km 网格和任务清单"],
        ["scripts/reproject_wgs84_to_utm50n.py", "行政区边界投影转换"],
        ["scripts/prepare_labelme_images.py", "将四波段和 NDVI GeoTIFF 转为 Labelme 主图和辅助图，并隔离全零数据"],
        ["scripts/fetch_jiangxia_tci_sources.py", "补充下载 Sentinel 2 真彩色整景并裁剪三个网格"],
        ["scripts/fetch_jiangxia_sentinel_chips.py", "尝试按窗口读取公开 Sentinel 2 四波段；当前网络范围读取不稳定，且 6 月候选出现全零，不能视为完成"],
        ["data/catalog/oge_asset_registry.csv", "OGE 平台和用户资源的权威注册表"],
        ["data/catalog/sentinel2_inventory.csv", "Sentinel 2 场景元数据和平台验证状态"],
        ["data/catalog/jiangxia_algorithm_dataset.csv", "三个网格五时相 NDVI 平台导出任务清单；需补充内容质量状态"],
        ["data/catalog/jiangxia_multispectral_dataset.csv", "四波段平台导出任务清单；需补充内容质量状态"],
        ["docs/experiment-log.md", "平台试验时间线和操作结论"],
        ["docs/rice-label-strategy.md", "标签类别、样区分工和训练验证隔离原则"],
        ["backend/app", "FastAPI 业务后台最小原型"],
    ], widths=[3.1, 3.8], font_size=9)

    add_heading(doc, "九 已知问题与风险", 1)
    add_table(doc, ["风险", "当前证据", "处理要求"], [
        ["早中期 OGE 导出文件全零", "9 组 MS4 和 NDVI 虽然任务完成且文件尺寸正常，但像元全部为零", "禁止用于标注和训练；替换时相后重新做像元级和目视检查"],
        ["数据清单状态过于乐观", "旧清单使用 export completed，未区分内容有效性", "增加内容检查字段并更正旧状态"],
        ["武汉一号权限不稳定", "多次复测返回无使用权限", "Sentinel 2 保持首版主线；权限恢复后再加入武汉一号增强"],
        ["代表样区的场景覆盖仍需论证", "目前三个网格按南部、中西部和东北部选择，尚未形成完整地貌分层证据", "结合地形、土地覆盖和水稻分布进一步检查代表性"],
        ["灌溉定额尚未落地", "当前只有字段模板和方法口径，没有示范区正式分阶段定额", "开发演示可用明确标注的示例值；正式结果必须替换为有来源的参数"],
        ["没有实际取供水数据", "缺少水量、计量位置、服务范围和作物归属", "首期只做参考需水，不开展实际供需和节水效果评价"],
        ["平台批处理队列拥堵", "刷新后仍曾提示队列已满", "采用小批次提交，保存任务编号；必要时错峰运行"],
        ["前端和服务发布尚未开始", "只有后台适配代码和技术路线", "先稳定识别输入输出，再完成 OGE 服务发布和前后端联调"],
    ], widths=[1.65, 3.0, 2.25], font_size=9)

    add_heading(doc, "十 建议的后续执行顺序", 1)
    add_heading(doc, "第一优先级 冻结可标注数据包", 2)
    add_numbered(doc, [
        "为 6 月和 7 月选择覆盖三个网格且像元有效的替代场景。必要时检查 T49RGP 相邻瓦片或调整代表网格。",
        "形成三个网格和五个时相的最终清单。每个时相至少有可正常显示的 RGB 主图；若用于模型输入，还需提供统一波段组合。",
        "逐文件检查尺寸、坐标系、像元最小值与最大值、有效像元比例、云和云影、亮度及空间对齐。",
        "重新运行 prepare_labelme_images.py，生成 15 张主标注图和相应辅助图。",
        "生成总览图并人工查看全部图像，确认没有全黑、全白、严重云遮挡、错位或异常拉伸。",
        "更新两个数据清单和实验记录，标注 accepted、rejected 和替代原因。完成这些步骤后再通知团队开始标注。",
    ])
    add_heading(doc, "第二优先级 制作标签和验证基线", 2)
    add_numbered(doc, [
        "先在 R03C06 完成小范围水稻和非水稻标注，制定统一判读规则。",
        "使用 semanticricefield 或其他可用平台模型生成伪标签，检查其输入波段、分辨率和类别含义。",
        "在 R07C05 补充难例；R10C10 保留为独立验证。",
        "计算精确率、召回率和 F1，并记录模型、数据和样本版本。",
    ])
    add_heading(doc, "第三优先级 打通业务链路", 2)
    add_numbered(doc, [
        "将稳定的遥感流程发布为 OGE 可调用服务。",
        "在后台建立任务提交、状态查询和成果获取流程。",
        "接入作物历和分阶段灌溉定额，完成阶段参考需水计算和关注等级。",
        "基于官方全栈模板开发 Web 页面并完成典型区域演示。",
    ])

    add_heading(doc, "十一 团队接手检查清单", 1)
    add_bullets(doc, [
        "不要使用 tolabel 下 _invalid_zero_source 中的任何图像。",
        "不要把平台任务状态已完成等同于数据合格。",
        "不要把耕地候选区写成水稻识别结果。",
        "不要把参考灌溉需水量写成实际用水量。",
        "不要把公开行政区边界写成灌区供水服务边界。",
        "不要将 OGE Token、AppKey 或其他凭证提交到 Git。",
        "大幅原始影像和整景缓存不进入 Git，只提交清单、脚本、参数和小型示例。",
        "新增 OGE 场景必须记录 product ID、coverage ID、日期、云量、分析区有效性和验证状态。",
        "新增导出成果必须保存坐标系、分辨率、波段顺序、任务编号、文件位置和内容检查结果。",
    ])

    add_heading(doc, "十二 当前可交付成果", 1)
    add_table(doc, ["成果", "状态"], [
        ["比赛方案和业务闭环设计", "已完成初版并多轮调整"],
        ["GitHub 仓库和本地工程结构", "已建立并已推送基础版本"],
        ["FastAPI 业务后台最小原型", "已实现"],
        ["江夏区公开边界和投影边界", "已准备并已在 OGE 验证读取"],
        ["江夏区 5 km 网格和处理任务清单", "已生成"],
        ["Sentinel 2 时序场景清单", "已建立，但需按最新内容检查结果修订"],
        ["OGE 小网格裁剪、NDVI 和批处理导出链路", "已验证"],
        ["三个代表网格的 8 月和 10 月标注数据", "6 张主图已通过检查"],
        ["4 月 18 日三个网格真彩色源图", "已裁剪，待并入最终标注集"],
        ["完整 15 张标注主图", "未完成，当前暂停在替换无效 6 月时相"],
        ["水稻最终模型和精度报告", "未开始"],
        ["OGE 服务发布和第三方 Web 系统", "未开始正式联调"],
    ], widths=[3.6, 3.3])

    add_heading(doc, "十三 交接后的第一项工作", 1)
    add_para(doc, "恢复开发后，第一项工作不是立即标注或训练，而是完成三个代表网格五时相数据包的质量冻结。当前建议从 6 月替代场景入手，检查江夏三个网格在 T50RKU 和相邻瓦片中的有效覆盖；随后复核 7 月 5 日公开同源影像。只有 15 张主图全部通过自动检查和人工总览，才进入 Labelme 标注。")
    add_para(doc, "截至本交接日期，补齐任务已按用户要求暂停，没有后台下载或平台批处理继续运行。已下载的 4 月、6 月和 7 月整景真彩色缓存保存在 source_geotiff/_scene_cache，可在后续继续使用，无需重新下载。")

    # Footer
    for sec in doc.sections:
        footer = sec.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = footer.add_run("禾灌智析项目开发交接文档  2026 年 11 月 5 日")
        set_font(r, size=9, color="666666")

    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
