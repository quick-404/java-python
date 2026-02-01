package com.example.ast;

import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ParserConfiguration.LanguageLevel;
import com.github.javaparser.StaticJavaParser;

import com.github.javaparser.ast.*;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.comments.*;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.nodeTypes.*;
import com.github.javaparser.ast.stmt.*;

import java.io.File;
import java.io.FileWriter;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/**
 * Main.java — 方案B：通用建树 + 轻量增强器（多版本兼容）
 *
 * 用法：
 *   java com.example.ast.Main [inputDir] [outputJson]
 * 默认：
 *   inputDir  = "D:\\27201\\AST\\src\\basic"
 *   outputJson= "output/ast_Demo.json"
 */
public class Main {

    // ============== 数据模型 ==============
    public static class ASTNode {
        public String type;
        public String name;
        public int line = -1;
        public int column = -1;
        public int endLine = -1;
        public int endColumn = -1;
        public String value;
        public Map<String, String> attrs = new LinkedHashMap<>();
        public List<ASTNode> children = new ArrayList<>();

        public ASTNode(String type, String name) {
            this.type = type;
            this.name = name;
        }
        public void setLine(int line) { this.line = line; }
        public void setColumn(int col) { this.column = col; }
        public void setEndLine(int endLine) { this.endLine = endLine; }
        public void setEndColumn(int endColumn) { this.endColumn = endColumn; }
        public void setValue(String value) { this.value = value; }
        public void addChild(ASTNode node) { children.add(node); }
        public void putAttr(String k, String v) {
            if (k != null && v != null) attrs.put(k, v);
        }
    }

    // ============== 主入口 ==============
    public static void main(String[] args) {
        try {
            ParserConfiguration config = new ParserConfiguration()
                    .setLanguageLevel(LanguageLevel.BLEEDING_EDGE)
                    .setAttributeComments(true);
            StaticJavaParser.setConfiguration(config);

            String inputDirPath = (args.length >= 1) ? args[0] : "D:\\27201\\AST\\src\\basic";
            String outputPathStr = (args.length >= 2) ? args[1] : "output/ast_Demo.json";

            File inputDir = new File(inputDirPath);
            if (!inputDir.exists() || !inputDir.isDirectory()) {
                System.err.println("输入目录不存在或不是目录: " + inputDirPath);
                return;
            }

            final boolean enableStrTemplateDowngrade = false;

            ASTNode root = new ASTNode("Project", "Project");

            Files.walk(Paths.get(inputDirPath))
                    .filter(Files::isRegularFile)
                    .filter(p -> p.toString().endsWith(".java"))
                    .forEach(path -> {
                        System.out.println("Parsing: " + path);
                        try {
                            String raw = Files.readString(path, StandardCharsets.UTF_8);
                            String pre = enableStrTemplateDowngrade ? safeDegradeStrTemplates(raw) : raw;

                            CompilationUnit cu = StaticJavaParser.parse(pre);

                            ASTNode fileNode = new ASTNode("File", path.getFileName().toString());
                            fileNode.setValue(path.toString());
                            root.addChild(fileNode);

                            ASTNode cuNode = buildTree(cu);
                            fileNode.addChild(cuNode);

                            // 孤儿注释，挂在文件级
                            try {
                                for (Comment c : cu.getOrphanComments()) {
                                    ASTNode cNode = commentNode(c, "OrphanComment");
                                    fileNode.addChild(cNode);
                                }
                            } catch (Throwable ignored) {}

                        } catch (Exception e) {
                            System.err.println("Failed to parse " + path + " → " + e.getMessage());
                            e.printStackTrace();
                        }
                    });

            Path outputPath = Paths.get(outputPathStr);
            Path outputDir = outputPath.getParent();
            if (outputDir != null && !Files.exists(outputDir)) {
                Files.createDirectories(outputDir);
            }

            String json = toJson(root);
            try (FileWriter writer = new FileWriter(outputPath.toFile(), StandardCharsets.UTF_8)) {
                writer.write(json);
            }
            System.out.println("JSON 已写入: " + outputPath.toAbsolutePath());

        } catch (Exception e) {
            System.err.println("发生错误: " + e.getMessage());
            e.printStackTrace();
        }
    }

    // ============== 通用建树 + 增强（多版本兼容） ==============

    private static ASTNode buildTree(Node n) {
        String kind = n.getClass().getSimpleName();
        String name = extractName(n);
        ASTNode out = new ASTNode(kind, name);

        setRangeFull(n, out);
        attachDirectComment(n, out);
        enhanceCompat(out, n); // 关键节点增强（兼容不同版本命名/签名）

        for (Node child : n.getChildNodes()) {
            out.addChild(buildTree(child));
        }
        return out;
    }

    /** 兼容模式增强：尽量不直接引用易变类，使用反射读取属性 */
    private static void enhanceCompat(ASTNode out, Node n) {
        String kind = n.getClass().getSimpleName();

        boolean handled = handleVariantNodes(out, n, kind);
        handled = handleStructuredNodes(out, n) || handled;

        attachCommonAttributes(out, n);
        if (!handled) {
            attachLightweightAttributes(out, n);
        }
    }

    private static boolean handleVariantNodes(ASTNode out, Node n, String kind) {
        // 先处理“类名会变”的节点：ForEach/Foreach、SwitchEntry/Stmt、SwitchExpr、RecordDeclaration、YieldStmt、ModuleDeclaration
        if ("ForEachStmt".equals(kind) || "ForeachStmt".equals(kind)) {  // 两个拼写同时覆盖
            Object var = invokeNoArg(n, "getVariable");
            Object iter = invokeNoArg(n, "getIterable");
            out.putAttr("var", toStr(var));
            out.putAttr("iterable", toStr(iter));
            return true;
        }

        if ("SwitchExpr".equals(kind)) {
            Object sel = invokeNoArg(n, "getSelector");
            out.putAttr("selector", toStr(sel));
            return true;
        }

        if ("SwitchEntry".equals(kind) || "SwitchEntryStmt".equals(kind)) {
            Object labels = invokeNoArg(n, "getLabels");  // 新版有 labels（列表）
            if (labels != null) {
                out.putAttr("labels", labels.toString());
            } else {
                Object label = invokeNoArg(n, "getLabel"); // 旧版是单个 label 或 null=default
                out.putAttr("labels", toStr(label));
            }
            return true;
        }

        if ("RecordDeclaration".equals(kind)) {
            out.setValue("record");
            Object params = invokeNoArg(n, "getParameters");
            out.putAttr("components", toStr(params));
            out.putAttr("modifiers", toStr(invokeNoArg(n, "getModifiers")));
            out.putAttr("annotations", toStr(invokeNoArg(n, "getAnnotations")));
            return true;
        }

        if ("YieldStmt".equals(kind)) {
            Object expr = invokeNoArg(n, "getExpression");
            out.putAttr("expr", toStr(expr));
            return true;
        }

        if ("ModuleDeclaration".equals(kind)) {
            out.putAttr("name", toStr(invokeNoArg(n, "getNameAsString")));
            Object isOpen = invokeNoArg(n, "isOpen");
            if (isOpen != null) out.putAttr("isOpen", String.valueOf(isOpen));
            return true;
        }
        return false;
    }

    private static boolean handleStructuredNodes(ASTNode out, Node n) {
        // 处理“稳定类”的增强（直接 instanceof）
        if (n instanceof ClassOrInterfaceDeclaration c) {
            out.setValue(c.isInterface() ? "interface" : "class");
            out.putAttr("modifiers", c.getModifiers().toString());
            out.putAttr("typeParams", c.getTypeParameters().toString());
            out.putAttr("extends", c.getExtendedTypes().toString());
            out.putAttr("implements", c.getImplementedTypes().toString());
            out.putAttr("annotations", c.getAnnotations().toString());
            return true;
        }

        if (n instanceof EnumDeclaration e) {
            out.putAttr("modifiers", e.getModifiers().toString());
            out.putAttr("implements", e.getImplementedTypes().toString());
            out.putAttr("annotations", e.getAnnotations().toString());
            return true;
        }

        if (n instanceof AnnotationDeclaration ad) {
            out.setValue("@interface");
            out.putAttr("modifiers", ad.getModifiers().toString());
            out.putAttr("annotations", ad.getAnnotations().toString());
            return true;
        }

        if (n instanceof EnumConstantDeclaration ecd) {
            out.putAttr("args", ecd.getArguments().toString());
            out.putAttr("hasClassBody", String.valueOf(!ecd.getClassBody().isEmpty()));
            out.putAttr("annotations", ecd.getAnnotations().toString());
            return true;
        }

        if (n instanceof AnnotationMemberDeclaration amd) {
            out.putAttr("type", amd.getType().toString());
            out.putAttr("default", amd.getDefaultValue().map(Object::toString).orElse(""));
            out.putAttr("modifiers", amd.getModifiers().toString());
            out.putAttr("annotations", amd.getAnnotations().toString());
            return true;
        }

        if (n instanceof InitializerDeclaration init) {
            out.putAttr("isStatic", String.valueOf(init.isStatic()));
            return true;
        }

        if (n instanceof MethodDeclaration m) {
            out.setValue(m.getType().asString());
            out.putAttr("modifiers", m.getModifiers().toString());
            out.putAttr("typeParams", m.getTypeParameters().toString());
            out.putAttr("throws", m.getThrownExceptions().toString());
            out.putAttr("annotations", m.getAnnotations().toString());
            return true;
        }

        if (n instanceof ConstructorDeclaration c) {
            out.putAttr("modifiers", c.getModifiers().toString());
            out.putAttr("throws", c.getThrownExceptions().toString());
            out.putAttr("annotations", c.getAnnotations().toString());
            return true;
        }

        if (n instanceof FieldDeclaration f) {
            out.setValue(f.getElementType().asString());
            out.putAttr("modifiers", f.getModifiers().toString());
            out.putAttr("annotations", f.getAnnotations().toString());
            return true;
        }

        if (n instanceof VariableDeclarator v) {
            out.setValue(v.getType().asString());
            v.getInitializer().ifPresent(init -> out.putAttr("initializer", init.toString()));
            return true;
        }

        if (n instanceof LambdaExpr le) {
            out.putAttr("params", le.getParameters().toString());
            out.putAttr("isEnclosingParameters", String.valueOf(le.isEnclosingParameters()));
            out.putAttr("isExpressionBody", String.valueOf(le.getBody().isExpressionStmt()));
            return true;
        }

        if (n instanceof MethodReferenceExpr mr) {
            out.putAttr("scope", mr.getScope().toString());
            out.putAttr("identifier", mr.getIdentifier());
            out.putAttr("typeArgs", mr.getTypeArguments().map(Object::toString).orElse(""));
            return true;
        }

        if (n instanceof ObjectCreationExpr oce) {
            out.putAttr("type", oce.getType().asString());
            out.putAttr("hasAnonymousClassBody", String.valueOf(oce.getAnonymousClassBody().isPresent()));
            return true;
        }

        if (n instanceof IfStmt is) {
            out.putAttr("condition", is.getCondition().toString());
            return true;
        }

        if (n instanceof ForStmt fs) {
            out.putAttr("init", fs.getInitialization().toString());
            // getCompare() 旧版返回 Expression，新版返回 Optional<Expression> —— 用反射统一拿字符串
            String compareStr = "";
            try {
                Method m = n.getClass().getMethod("getCompare");
                Object cmp = m.invoke(n);
                compareStr = (cmp instanceof Optional)
                        ? ((Optional<?>) cmp).map(Object::toString).orElse("")
                        : (cmp == null ? "" : cmp.toString());
            } catch (Throwable ignored) {}
            out.putAttr("compare", compareStr);
            out.putAttr("update", fs.getUpdate().toString());
            return true;
        }

        if (n instanceof WhileStmt ws) {
            out.putAttr("condition", ws.getCondition().toString());
            return true;
        }

        if (n instanceof DoStmt ds) {
            out.putAttr("condition", ds.getCondition().toString());
            return true;
        }

        if (n instanceof SwitchStmt ss) {
            out.putAttr("selector", ss.getSelector().toString());
            return true;
        }

        if (n instanceof CatchClause cc) {
            out.putAttr("paramType", cc.getParameter().getType().asString());
            return true;
        }

        if (n instanceof TryStmt t) {
            out.putAttr("resources", t.getResources().toString());
            return true;
        }

        if (n instanceof ReturnStmt rs) {
            out.putAttr("expr", rs.getExpression().map(Object::toString).orElse(""));
            return true;
        }

        if (n instanceof ThrowStmt ts) {
            out.putAttr("expr", ts.getExpression().toString());
            return true;
        }

        if (n instanceof AssertStmt as) {
            out.putAttr("check", as.getCheck().toString());
            out.putAttr("message", as.getMessage().map(Object::toString).orElse(""));
            return true;
        }

        if (n instanceof BreakStmt bs) {
            out.putAttr("label", bs.getLabel().map(SimpleName::asString).orElse(""));
            return true;
        }

        if (n instanceof ContinueStmt cs) {
            out.putAttr("label", cs.getLabel().map(SimpleName::asString).orElse(""));
            return true;
        }

        if (n instanceof LabeledStmt ls) {
            out.putAttr("label", ls.getLabel().asString());
            return true;
        }
        return false;
    }

    private static void attachCommonAttributes(ASTNode out, Node n) {
        putAttrIfAbsent(out, "modifiers", extractModifiers(n));

        if (n instanceof NodeWithType<?, ?> withType) {
            putAttrIfAbsent(out, "type", withType.getType().toString());
        }

        if (n instanceof NodeWithParameters<?> withParams) {
            putAttrIfAbsent(out, "params", withParams.getParameters().toString());
        }

        if (n instanceof NodeWithTypeArguments<?> withTypeArgs) {
            withTypeArgs.getTypeArguments().ifPresent(args ->
                    putAttrIfAbsent(out, "typeArgs", args.toString())
            );
        }

        if (n instanceof NodeWithArguments<?> withArgs) {
            putAttrIfAbsent(out, "args", withArgs.getArguments().toString());
        }

        if (n instanceof ImportDeclaration id) {
            putAttrIfAbsent(out, "name", id.getNameAsString());
            putAttrIfAbsent(out, "isStatic", String.valueOf(id.isStatic()));
            putAttrIfAbsent(out, "isAsterisk", String.valueOf(id.isAsterisk()));
        }

        if (n instanceof PackageDeclaration pd) {
            putAttrIfAbsent(out, "name", pd.getNameAsString());
        }
    }

    private static void attachLightweightAttributes(ASTNode out, Node n) {
        try {
            if (n instanceof SynchronizedStmt sync) {
                out.putAttr("expr", sync.getExpression().toString());
            } else if (n instanceof com.github.javaparser.ast.stmt.ExpressionStmt es) {
                out.putAttr("code", es.getExpression().toString());
            } else if (n instanceof com.github.javaparser.ast.expr.MethodCallExpr mc) {
                out.putAttr("code", mc.toString());
                out.putAttr("args", mc.getArguments().toString());
            } else if (n instanceof com.github.javaparser.ast.expr.AssignExpr ae) {
                out.putAttr("code", ae.toString());
            } else if (n instanceof com.github.javaparser.ast.expr.VariableDeclarationExpr vde) {
                out.putAttr("code", vde.toString());
            } else if (n instanceof com.github.javaparser.ast.stmt.CatchClause cc) {
                out.putAttr("paramType", cc.getParameter().getType().asString());
            } else if (n instanceof com.github.javaparser.ast.body.Parameter p) {
                out.putAttr("type", p.getType().asString());
                out.putAttr("isVarArgs", String.valueOf(p.isVarArgs()));
                out.putAttr("modifiers", p.getModifiers().toString());
                out.putAttr("annotations", p.getAnnotations().toString());
            }
        } catch (Throwable ignore) {}
    }


    private static String extractName(Node n) {
        try {
            if (n instanceof NodeWithSimpleName<?> s) return s.getNameAsString();
        } catch (Throwable ignored) {}
        try {
            if (n instanceof NodeWithName<?> nn) return nn.getNameAsString();
        } catch (Throwable ignored) {}

        if (n instanceof IfStmt is) return "if(" + snippet(is.getCondition()) + ")";
        if (n instanceof WhileStmt ws) return "while(" + snippet(ws.getCondition()) + ")";
        if (n instanceof DoStmt ds) return "do-while(" + snippet(ds.getCondition()) + ")";
        if (n instanceof SwitchStmt ss) return "switch(" + snippet(ss.getSelector()) + ")";
        if (n instanceof ForStmt) return "for(…)";
        if ("ForEachStmt".equals(n.getClass().getSimpleName()) || "ForeachStmt".equals(n.getClass().getSimpleName()))
            return "for-each(…)";
        if (n instanceof TryStmt) return "try";
        if (n instanceof CatchClause cc) return "catch(" + cc.getParameter().getType().asString() + ")";
        if (n instanceof ReturnStmt) return "return";
        if (n instanceof ThrowStmt) return "throw";
        if (n instanceof SynchronizedStmt) return "synchronized";
        if (n instanceof LabeledStmt ls) return ls.getLabel().asString() + ":";
        if (n instanceof MethodReferenceExpr mr) return mr.getIdentifier() + "::";
        if (n instanceof ObjectCreationExpr oce) return "new " + oce.getType().asString();
        return "";
    }

    private static String snippet(Expression e) {
        String s = e.toString();
        return (s.length() > 60) ? s.substring(0, 57) + "..." : s;
    }

    private static void attachDirectComment(Node n, ASTNode out) {
        try {
            n.getComment().ifPresent(c -> out.addChild(commentNode(c, kindOf(c))));
        } catch (Throwable ignored) {}
    }

    private static String extractModifiers(Node n) {
        try {
            if (n instanceof NodeWithModifiers<?> m) {
                return m.getModifiers().toString();
            }
        } catch (Throwable ignored) {}
        return "";
    }

    private static void putAttrIfAbsent(ASTNode node, String key, String value) {
        if (value == null || value.isEmpty()) return;
        if (!node.attrs.containsKey(key)) {
            node.putAttr(key, value);
        }
    }

    private static ASTNode commentNode(Comment c, String type) {
        ASTNode node = new ASTNode(type, "");
        node.setValue(c.getContent());
        setRangeFull(c, node);
        return node;
    }

    private static String kindOf(Comment c) {
        if (c instanceof JavadocComment) return "Javadoc";
        if (c instanceof LineComment) return "LineComment";
        if (c instanceof BlockComment) return "BlockComment";
        return "Comment";
    }

    private static void setRangeFull(Node n, ASTNode out) {
        n.getRange().ifPresent(r -> {
            out.setLine(r.begin.line);
            out.setColumn(r.begin.column);
            out.setEndLine(r.end.line);
            out.setEndColumn(r.end.column);
        });
    }

    // ============== JSON 序列化 ==============

    private static String toJson(ASTNode node) {
        return toJsonNode(node, 0);
    }

    private static String toJsonNode(ASTNode node, int indent) {
        String indentStr = "  ".repeat(indent);
        String childIndentStr = "  ".repeat(indent + 1);
        StringBuilder sb = new StringBuilder();
        sb.append(indentStr).append("{\n");

        List<String> parts = new ArrayList<>();
        parts.add(childIndentStr + "\"type\": \"" + escapeJson(node.type) + "\"");
        parts.add(childIndentStr + "\"name\": \"" + escapeJson(node.name) + "\"");

        if (node.line != -1) parts.add(childIndentStr + "\"line\": " + node.line);
        if (node.column != -1) parts.add(childIndentStr + "\"column\": " + node.column);
        if (node.endLine != -1) parts.add(childIndentStr + "\"endLine\": " + node.endLine);
        if (node.endColumn != -1) parts.add(childIndentStr + "\"endColumn\": " + node.endColumn);
        if (node.value != null) parts.add(childIndentStr + "\"value\": \"" + escapeJson(node.value) + "\"");

        if (node.attrs != null && !node.attrs.isEmpty()) {
            StringBuilder ab = new StringBuilder();
            ab.append(childIndentStr).append("\"attrs\": {\n");
            int i = 0, n = node.attrs.size();
            for (Map.Entry<String, String> e : node.attrs.entrySet()) {
                ab.append(childIndentStr).append("  ")
                        .append("\"").append(escapeJson(e.getKey())).append("\": ")
                        .append("\"").append(escapeJson(e.getValue())).append("\"");
                if (i++ < n - 1) ab.append(",");
                ab.append("\n");
            }
            ab.append(childIndentStr).append("}");
            parts.add(ab.toString());
        }

        if (node.children != null && !node.children.isEmpty()) {
            StringBuilder cb = new StringBuilder();
            cb.append(childIndentStr).append("\"children\": [\n");
            for (int i = 0; i < node.children.size(); i++) {
                cb.append(toJsonNode(node.children.get(i), indent + 2));
                if (i < node.children.size() - 1) cb.append(",\n"); else cb.append("\n");
            }
            cb.append(childIndentStr).append("]");
            parts.add(cb.toString());
        }

        for (int i = 0; i < parts.size(); i++) {
            sb.append(parts.get(i));
            if (i < parts.size() - 1) sb.append(",\n"); else sb.append("\n");
        }
        sb.append(indentStr).append("}");
        return sb.toString();
    }

    /** 安全 JSON 转义：使用字符追加方式避免在源码中写出反斜杠+u */
    private static String escapeJson(String s) {
        if (s == null) return "";
        StringBuilder out = new StringBuilder(s.length() + 16);
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            switch (ch) {
                case '"':  out.append('\\').append('"');  break;
                case '\\': out.append('\\').append('\\'); break;
                case '\b': out.append('\\').append('b');  break;
                case '\f': out.append('\\').append('f');  break;
                case '\n': out.append('\\').append('n');  break;
                case '\r': out.append('\\').append('r');  break;
                case '\t': out.append('\\').append('t');  break;
                default:
                    if (ch < 0x20) { // 其他控制字符
                        out.append('\\').append('u');
                        String hex = Integer.toHexString(ch);
                        for (int k = hex.length(); k < 4; k++) out.append('0');
                        out.append(hex);
                    } else {
                        out.append(ch);
                    }
            }
        }
        return out.toString();
    }

    // ============== 反射与小工具 ==============

    /** 反射调用无参方法，失败返回 null */
    private static Object invokeNoArg(Object target, String method) {
        try {
            Method m = target.getClass().getMethod(method);
            m.setAccessible(true);
            return m.invoke(target);
        } catch (Throwable ignored) {
            return null;
        }
    }

    /** 将对象（含 Optional）转字符串 */
    private static String toStr(Object o) {
        if (o == null) return "";
        if (o instanceof Optional) {
            Optional<?> opt = (Optional<?>) o;
            return opt.map(Object::toString).orElse("");
        }
        return o.toString();
    }

    /**
     * 仅降级“纯文本常量”的 STR."..."：不含 ${…}。否则保持原样。
     */
    private static String safeDegradeStrTemplates(String src) {
        StringBuilder out = new StringBuilder(src.length());
        int i = 0, n = src.length();
        while (i < n) {
            if (i + 5 <= n && src.startsWith("STR.\"", i)) {
                int j = i + 5;
                boolean escaped = false, ok = false, hasInterp = false;
                while (j < n) {
                    char c = src.charAt(j);
                    if (!escaped && c == '$' && j + 1 < n && src.charAt(j + 1) == '{') hasInterp = true;
                    if (!escaped && c == '"') { ok = true; break; }
                    escaped = (!escaped && c == '\\');
                    j++;
                }
                if (ok && !hasInterp) {
                    out.append('"').append(src, i + 5, j).append('"');
                    i = j + 1;
                    continue;
                }
            }
            out.append(src.charAt(i++));
        }
        return out.toString();
    }
}
